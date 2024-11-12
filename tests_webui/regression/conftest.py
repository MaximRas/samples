import logging
from contextlib import suppress
from typing import Literal
from typing import Generator

import allure
import pytest
from boto3 import client as boto3_client
from selenium.common.exceptions import JavascriptException
from selenium.common.exceptions import WebDriverException

import consts
from tools import config
from tools.cameras import CameraData
from tools.cameras import CameraDoesNotExist
from tools.cameras import change_analytics
from tools.cameras import changed_cameras
from tools.cameras import clear_cameras_cache
from tools.cameras import create_camera
from tools.cameras import delete_camera
from tools.cameras import enable_camera
from tools.cameras import get_cameras
from tools.cameras import rename_camera
from tools.cameras import unarchive_camera
from tools.client import ApiClient
from tools.local_storage import LocalStorage
from tools.local_storage import clear_local_storage
from tools.locations import delete_location
from tools.locations import get_locations
from tools.mailinator import Inbox
from tools.mailinator import NoMailException
from tools.objects import change_cluster_name
from tools.objects import change_object_notes
from tools.search import search_api_v2
from tools.steps import get_head_objects
from tools.steps import prepare_cameras_for_suite
from tools.time_tools import change_timezone
from tools.users import auth_user_in_browser
from tools.users import change_password
from tools.users import change_user_name
from tools.users import change_user_state
from tools.users import delete_company
from tools.users import delete_user_from_company
from tools.users import delete_user_photo
from tools.users import get_active_company
from tools.users import get_active_user
from tools.users import get_available_companies
from tools.users import get_company_users
from tools.users import get_random_name
from tools.users import register_user
from tools.watchlists import delete_watchlist
from tools.watchlists import get_watchlists
from tools.webdriver import CustomWebDriver
from tools.webdriver import collect_browser_logs

log = logging.getLogger(__name__)


@pytest.fixture(scope='function', autouse=True)
def teardown_collect_logs(driver):
    yield
    collect_browser_logs(driver, check_uncaught_errors=True)


@pytest.fixture(scope='function')
def inbox(client, session_options):
    mailinator_inbox = Inbox(env=config.environment, email=client.user.email)
    return mailinator_inbox


@pytest.fixture(scope='function', autouse=True)
def teardown_complete_registration(client, inbox):
    yield
    try:
        while new_inbox := inbox._new_inboxes.pop():
            with suppress(NoMailException):
                register_user(
                    client,
                    new_inbox,
                    first_name=get_random_name('First'),
                    last_name=get_random_name('Last'),
                    timeout=5,
                )
            new_inbox.clear()
    except IndexError:
        pass


@pytest.fixture(scope='function')
def create_temporary_camera(client):
    cameras: list[CameraData] = []

    def _create_camera(name: str) -> CameraData:
        with allure.step(f'Create temporary camera {name}'):
            log.info(f'Create temporary camera {name}')
            cameras.append(create_camera(client, name))
            enable_camera(client, cameras[0])
            return cameras[0]

    yield _create_camera

    with allure.step(f'Delete temporary {cameras[0]}'):
        try:
            delete_camera(client, cameras[0])
        except CameraDoesNotExist:
            log.warning(f'Camera does not exit: {cameras[0]}')


@pytest.fixture(scope="function", autouse=True)
def teardown_local_storage(driver):
    yield
    with allure.step('Local Storage: clear all keys except tokens'):
        try:
            clear_local_storage(
                LocalStorage(driver),
                'main driver function teardown',
                exceptions=("refresh-token", "access-token", "user-company"),
            )
        except (JavascriptException, WebDriverException) as exc:
            log.error(f'Exception during clearing local storage: {exc}')


@pytest.fixture(scope="function")
def teardown_delete_locations(client):
    yield
    log.info('Delete locations')
    for loc in get_locations(client):
        delete_location(client, loc)


@pytest.fixture(scope="function")
def teardown_unarchive_cameras(teardown_enable_cameras, client: ApiClient) -> Generator[None, None, None]:
    '''
    We should use `teardown_enable_cameras` fixture due to: "Патч камеры с {archived=False} - камера должна быть разархивирована, статус активности (поле active) не изменяется"
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/device-manager/-/issues/104
    '''
    yield
    log.info('Unarchive cameras')
    for camera in changed_cameras.copy():
        try:
            unarchive_camera(client, camera, mark_as_changed=False)
        except CameraDoesNotExist:
            log.warning(f'{camera} does not exist any more')


@pytest.fixture(scope="function")
def teardown_disable_analytics_for_cameras(client):
    yield
    log.info('Disable analytics')
    for camera in changed_cameras.copy():
        change_analytics(client, camera, 'face', False,  mark_as_changed=False)
        change_analytics(client, camera, 'vehicle', False,  mark_as_changed=False)


@pytest.fixture(scope="function")
def teardown_rename_cameras(client):
    id_to_name = {c.id: c.name for c in get_cameras(client)}
    yield
    log.info('Rename cameras')
    for camera in get_cameras(client):
        expected_name = id_to_name[camera.id]
        if camera.name != expected_name:
            log.warning(f'Change camera name {camera.name} -> {expected_name}')
            rename_camera(client, camera, expected_name)


@pytest.fixture(scope='function')
def teardown_delete_cluster_names(client):
    yield

    with allure.step('Delete cluster names'):
        log.info(f'Delete cluster names for {client}')

        # clusters
        for base in consts.BASES_WITH_CLUSTERS:
            for item in get_head_objects(client, base):
                if item.meta['name']:
                    change_cluster_name(client, item, '')

        # single objects
        for base in consts.BASES_ALL:
            for item in search_api_v2(client, base, filters=consts.API_ANY_NAME):
                change_cluster_name(client, item, '')


@pytest.fixture(scope='function')
def teardown_delete_object_notes(client):
    yield

    with allure.step('Delete object notes'):
        log.info(f'Delete object notes for {client}')
        for base in ("face", "vehicle", "person"):
            for item in search_api_v2(client, base, consts.API_ANY_NOTES):
                change_object_notes(client, item, "")


@pytest.fixture(scope='function')
def teardown_restore_default_password(client, default_pwd):
    yield
    if client.user.current_password != default_pwd:
        change_password(client, new_password=default_pwd, old_password=client.user.current_password)
    else:
        log.info(f'{client} already has default password')


@pytest.fixture(scope='function')
def teardown_restore_name(client):
    user = get_active_user(client)
    first_name, last_name = user.first_name, user.last_name
    assert client.user.email == user.email  # self check
    yield
    change_user_name(client, first_name, last_name)


@pytest.fixture(scope='function')
def teardown_delete_user_photo(client):
    yield
    delete_user_photo(client)


@pytest.fixture(scope="function")
def teardown_delete_watchlists(client):
    yield
    with allure.step(f'Delete watchlists for {client}'):
        log.info(f'Delete watchlists for {client}')
        for watchlist in get_watchlists(client):
            delete_watchlist(client, watchlist)


@pytest.fixture(scope="function")
def teardown_restore_timezone(client):
    yield
    change_timezone(client, "America/Los_Angeles")


@pytest.fixture(scope="function")
def teardown_restore_default_zoom_in_search(client):
    yield
    with allure.step('Restore default zoom for search results'):
        log.info('Restore default zoom for search results')
        change_user_state(
            client,
            {
                'advancedSearch': {
                    # 'leftPanel': {'open': True},
                    # 'showMeta': True,
                    'zoom': {'value': 100},
                },
            }
        )


@pytest.fixture(scope='function')
def teardown_restore_default_camera_info_state(client: ApiClient) -> Generator[None, None, None]:
    yield
    with allure.step('Restore hide/show camera info state'):
        log.info(f'Restore hide/show camera info state for {client}')
        change_user_state(
            client,
            {
                "deviceTree": {
                    "showAnalytics": False,
                }
            }
        )


@pytest.fixture(scope="function")
def teardown_restore_show_object_information(client):
    yield
    with allure.step(f'Change "Show object info" state for {client}'):
        log.info(f'Change "Show object info" state for {client}')
        change_user_state(
            client,
            {
                'advancedSearch': {
                    'showMeta': True,
                },
            }
        )


@pytest.fixture(scope='function')
def teardown_restore_roi_state(client):
    yield
    with allure.step('Restore default value for ROI in search results'):
        log.info(f'Restore default value for ROI in search results for {client}')
        change_user_state(
            client, {
                "userState": {
                    "searchResults": {
                        "roi": 0,
                    }
                }
            }
        )


@pytest.fixture(scope='function')
def remove_other_companies(client: ApiClient):
    with allure.step(f'Remove all companies except active for {client}'):
        log.warning(f'Remove all companies except active for {client}')
        active_company = get_active_company(client)
        log.info(f'Active company is: {active_company}')
        for company in get_available_companies(client):
            if company.name != active_company.name:
                delete_company(client, company)


@pytest.fixture(scope='function')
def teardown_no_favorite_companies(client):
    yield
    with allure.step(f'Get rid of favorite companies for {client}'):
        log.info(f'Get rid of favorite companies for {client}')
        change_user_state(
            client,
            {
                'switchCompany': {
                    'favorites': [],
                }
            },
        )


@pytest.fixture(scope='function', autouse=True)
def cameras(client: ApiClient):
    yield prepare_cameras_for_suite(client, count=4)
    clear_cameras_cache()
    changed_camera_names = [cam.name for cam in changed_cameras]
    if changed_cameras:
        log.warning(f' - clear list of changed cameras: {changed_camera_names}')
        changed_cameras.clear()


@pytest.fixture(scope='function')
def temporary_change_access_token_validity(env_setup, metapix):
    def relogin():
        with allure.step('Relogin to obtain a new token'):
            log.info('Relogin to obtain a new token')
            clear_local_storage(
                LocalStorage(metapix.driver),
                'main driver relogin',
                exceptions=[],
            )
            auth_user_in_browser(metapix.driver)

    cognito = env_setup['cognito']
    cognito_client = boto3_client(
        "cognito-idp",
        aws_access_key_id=cognito["access_key"],
        aws_secret_access_key=cognito["secret_key"],
        region_name=cognito["region_name"],
    )
    data = cognito_client.describe_user_pool_client(
        UserPoolId=cognito["user_pool_id"],
        ClientId=cognito["app_id"],
    )['UserPoolClient']
    validity_value_before = data['AccessTokenValidity']
    validity_units_before = data['TokenValidityUnits']['AccessToken']
    log.info(f'Access token validity before: {validity_value_before} {validity_units_before}')

    def _change_validity_func(
            value: int,
            units: Literal['minutes'] | Literal['hours'] | Literal['days']) -> None:
        with allure.step(f'Change access token validity time -> {value} {units}'):
            log.info(f'Change access token validity time -> {value} {units}')
            cognito_client.update_user_pool_client(
                UserPoolId=cognito["user_pool_id"],
                ClientId=cognito["app_id"],
                AccessTokenValidity=value,
                TokenValidityUnits={"AccessToken": units},
            )
        relogin()

    yield _change_validity_func

    with allure.step(f'Restore default access token validity time: {validity_value_before} {validity_units_before}'):
        log.info(f'Restore default access token validity time: {validity_value_before} {validity_units_before}')
        _change_validity_func(validity_value_before, validity_units_before)


@pytest.fixture(scope='function')
def teardown_restore_driver_interceptors(driver: CustomWebDriver):
    yield
    with allure.step('Delete request/response interceptors'):
        log.info('Delete request/response interceptors')
        del driver.request_interceptor
        del driver.response_interceptor


@pytest.fixture(scope='function')
def teardown_restore_default_datetime_format(client: ApiClient) -> Generator[None, None, None]:
    yield
    with allure.step(f'Restore default datetime format for {client}'):
        log.info(f'Restore default datetime format for {client}')
        # TODO: parse DATETIME_FORMAT_DEFAULT to get parameters
        change_user_state(
            client,
            {
                'dateTime': {
                    'dateFormat': 'MM-DD-YYYY',
                    'timeFormat': '12-hour time',
                },
            }
        )
