import logging
from argparse import Namespace
from typing import Any
from typing import Generator
from typing import Mapping
from pathlib import Path

import allure
import pytest

from tools import CompanyInfoData
from tools import PreconditionException
from tools import RequestStatusCodeException
from tools import attach_screenshot
from tools import config
from tools.cameras import CameraDoesNotExist
from tools.cameras import change_camera_panel_state
from tools.cameras import enable_camera
from tools.cameras import changed_cameras
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.layouts import clear_layout
from tools.layouts import delete_layout
from tools.layouts import get_layouts
from tools.license_server import LicenseServerAPI
from tools.license_server import LicenseServerLicenseData
from tools.license_server import get_not_activated_licenses
from tools.local_storage import LocalStorage
from tools.local_storage import clear_local_storage
from tools.retry import retry
from tools.search import change_left_panel_state
from tools.tokens import delete_token
from tools.tokens import get_tokens
from tools.types import ApiUserRole
from tools.users import add_new_company
from tools.users import auth_client
from tools.users import auth_user_in_browser
from tools.users import get_second_company
from tools.users import set_active_company
from tools.webdriver import CustomWebDriver
from tools.webdriver import collect_browser_logs
from tools.webdriver import create_webdriver

from pages.base_page import PageDidNotLoaded
from pages.layout.layout_listbox import LayoutPage
from pages.root import RootPage

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@pytest.fixture(scope='session')
def license_server_data(env_setup: Mapping[str, Any]) -> Generator[Mapping[str, str], None, None]:
    return env_setup['license_server']


@pytest.fixture(scope='function')
def lic_server_admin(license_server_data: Mapping[str, str]) -> LicenseServerAPI:
    client = LicenseServerAPI(license_server_data['api_url'], license_server_data['admin'])
    return client


@pytest.fixture(scope='function')
def not_activated_license(lic_server_admin: LicenseServerAPI) -> LicenseServerLicenseData:
    not_activated = get_not_activated_licenses(lic_server_admin)
    log.info(f'Found {len(not_activated)} licenses available to activate')
    if len(not_activated) == 0:
        raise PreconditionException('There is no licenses available to activate')
    return not_activated[0]


@pytest.fixture(scope='module')
def sender(client: ApiClient) -> Generator[ImageSender, None, None]:
    sender = ImageSender(client)
    sender.init_objects()
    yield sender
    # TODO: check sender has correct amount of objects


@pytest.fixture(scope='module')
def use_search_during_choosing_company() -> bool:
    return False


@pytest.fixture(scope='module')
def driver(
        session_options: Namespace,
        client: ApiClient,
        use_search_during_choosing_company: bool,
) -> Generator[CustomWebDriver, None, None]:
    driver = create_webdriver(session_options)
    driver.client = client
    driver.is_just_created = True
    auth_user_in_browser(
        driver,
        client,
        use_search=use_search_during_choosing_company,
    )
    yield driver
    clear_local_storage(
        LocalStorage(driver),
        'main driver module teardown',
        exceptions=[],
    )
    driver.quit()


@pytest.fixture(scope='function')
def another_driver(session_options: Namespace, client: ApiClient) -> Generator[CustomWebDriver, None, None]:
    driver = create_webdriver(session_options, is_another_driver=True)
    driver.client = client
    yield driver
    clear_local_storage(
        LocalStorage(driver),
        'another driver teardown',
        exceptions=[],
    )
    collect_browser_logs(driver, check_uncaught_errors=True)
    driver.quit()


@pytest.fixture(scope='function')
def restore_session(driver: CustomWebDriver) -> Generator[None, None, None]:
    with allure.step(f'Save data for {driver.client}'):
        client_before = driver.client
        user_before = driver.client.user
        company_before = driver.client.company

    yield

    if id(driver.client) != id(client_before):
        driver.client = client_before
        log.warning(f'Log out (by clearing local storage) since client has been changed: {driver.client} -> {client_before}')
        clear_local_storage(
            LocalStorage(driver),
            'main driver restore client',
            exceptions=[],
        )
    elif driver.client.user != user_before or driver.client.company != company_before:
        log.warning('Log out (by clearing local storage) since user or company have been changed')
        auth_client(
            driver.client,
            email=user_before.email,
            password=config.user_config['_default_pwd'],
        )
        if driver.client.user != user_before:
            driver.client.set_user(user_before)
        if driver.client.company != company_before:
            set_active_company(driver.client, company_before)
        clear_local_storage(
            LocalStorage(driver),
            'main driver restore user or company',
            exceptions=[],
        )


@pytest.fixture(scope='function')
def metapix(
        driver: CustomWebDriver,
        client: ApiClient,
        restore_session) -> Generator[RootPage, None, None]:

    class LoggedOutException(Exception):
        pass

    @retry(LoggedOutException)
    def _open_root():
        try:
            root_page = RootPage(driver, open_page=True)
            return root_page
        except PageDidNotLoaded as exc:
            # FYI: RuntimeError(f'No company with name: "{name}"') may happen here
            log.warning('Unexpected behavior: it is not possible to open root page')
            attach_screenshot(driver, 'metapix: it is not possible to open root page')
            auth_user_in_browser(driver, client)
            raise LoggedOutException from exc

    if driver.is_just_created:
        log.info('Assume root page has been just opened. Do not open root page')
        driver.is_just_created = False
        yield RootPage(driver=driver, open_page=False)
    else:
        log.info(f'Open root page for {client}')
        yield _open_root()


@pytest.fixture(scope='function')
def second_company(
        client: ApiClient,
        metapix: RootPage) -> Generator[CompanyInfoData, None, None]:
    role = ApiUserRole.admin
    if (company := get_second_company(client, role=role)) is None:
        company = add_new_company(client, role=role)
        metapix.refresh()  # make sure 'Switch Company' button appears
    yield company


@pytest.fixture(scope="function")
def teardown_delete_tokens(client: ApiClient) -> Generator[None, None, None]:
    yield
    log.info('Delete tokens')
    for token in get_tokens(client):
        delete_token(client, token)


@pytest.fixture(scope="function")
def teardown_enable_cameras(client: ApiClient) -> Generator[None, None, None]:
    yield
    for camera in changed_cameras.copy():
        try:
            enable_camera(client, camera, mark_as_changed=False)
        except RequestStatusCodeException as exc:
            log.error(f"Can't activate {camera}: {exc}")
        except CameraDoesNotExist:
            log.warning(f'{camera} does not exist any more')


@pytest.fixture(scope='function')
def teardown_delete_layouts(client: ApiClient) -> Generator[None, None, None]:
    """ Delete all layouts except "Default". Delete all widgets from "Default" layout """
    yield

    with allure.step('Delete all layouts except default'):
        log.info('Delete all layouts except default')
        default_has_been_found = False
        for layout in get_layouts(client):
            if layout.name == LayoutPage.DEFAULT_LAYOUT_NAME and default_has_been_found is False and not layout.shared:
                clear_layout(client, layout)
                default_has_been_found = True
            else:
                delete_layout(client, layout)


@pytest.fixture(scope="function")
def teardown_search_show_filters_panel(client: ApiClient) -> Generator[None, None, None]:
    yield
    change_left_panel_state(client, state=True)


@pytest.fixture(scope="function")
def teardown_device_tree_show_cameras_panel(client: ApiClient) -> Generator[None, None, None]:
    yield
    change_camera_panel_state(client, state=True)


@pytest.fixture(scope="function")
def teardown_delete_network_conditions(driver: CustomWebDriver) -> Generator[None, None, None]:
    yield
    with allure.step(f'Delete network conditions for {driver}'):
        log.info(f'Delete network conditions for {driver}')
        driver.delete_network_conditions()


def pytest_addoption(parser):
    parser.addoption('--headless', action='store_true', help='Run webdriver in headless mode')
    parser.addoption('--record-video', action='store_true', help='Record low fps video (from selenium screenshots)')
    parser.addoption('--webdriver', type=str, default="chrome")
    parser.addoption('--custom-web-url', type=str, default='')
    parser.addoption('--profile-dir', type=Path, default=None)
