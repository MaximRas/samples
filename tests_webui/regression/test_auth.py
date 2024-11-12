import logging
import time
from typing import Callable
from typing import Mapping
from typing import Any

import allure
import pytest
import jwt
from seleniumwire.request import Request

from tools import PreconditionException
from tools.cameras import delete_all_cameras_for_client
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.local_storage import LocalStorage
from tools.mailinator import Inbox
from tools.steps import check_email_validation
from tools.steps import check_input_is_disabled
from tools.steps import check_input_validation
from tools.steps import check_password_validation
from tools.steps import create_any_chart
from tools.steps import create_any_widget
from tools.time_tools import now_pst
from tools.time_tools import timestamp_to_date
from tools.types import TimestampType
from tools.types import TokenType
from tools.types import EmailType
from tools.users import CompanyInfoData
from tools.users import auth_user_in_browser
from tools.users import get_available_companies
from tools.users import get_company_title
from tools.webdriver import CustomWebDriver

from pages.base_page import is_element_exist
from pages.base_page import PageDidNotLoaded
from pages.dashboard import DashboardPage
from pages.dashboard import widget_class_shared
from pages.device_tree import NO_CAMERAS
from pages.login import LoginPage
from pages.root import RootPage
from pages.switch_company import SwitchSystemDialog

from tests_webui.regression import check_show_password_ico

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def login_page(metapix: RootPage):
    return metapix.logout()


def get_access_token(driver: CustomWebDriver) -> TokenType:
    local_storage = LocalStorage(driver)
    return local_storage.get('access-token')


def decode_token(token: TokenType) -> Mapping[str, Any]:
    decoded_access_token = jwt.decode(token, options={"verify_signature": False})
    return decoded_access_token


def get_time_to_expire(exp_timestamp: TimestampType) -> float:
    ''' returns minutes '''
    diff = timestamp_to_date(exp_timestamp) - now_pst()
    return diff.total_seconds()


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into metapix as user with one company")
@pytest.mark.usefixtures('remove_other_companies')
def test_login_with_one_company_to_dashboard(login_page, client, driver):
    if len(get_available_companies(client)) != 1:
        raise PreconditionException(f'{client} has to have only one company')
    metapix = login_page.login()

    avatar_menu = metapix.open_avatar_menu()
    assert avatar_menu.company_name == get_company_title(driver)


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into shared widget as user with one company")
@pytest.mark.usefixtures('teardown_delete_layouts')
@pytest.mark.usefixtures('remove_other_companies')
def test_login_with_one_company_to_shared_widget(
        metapix: RootPage,
        client: ApiClient,
        another_driver: CustomWebDriver,
        sender: ImageSender):
    if len(get_available_companies(client)) != 1:
        raise PreconditionException(f'{client} has to have only one company')
    sender.check_min_objects_count({"face": 2})
    widget = create_any_chart(metapix.dashboard, 'face')
    login_page = widget.share(another_driver, return_page=LoginPage)
    shared_widget = login_page.login(
        ignore_choosing_company=False,
        choose_default_company=False,
        return_page=widget_class_shared[widget.type],
    )
    assert shared_widget.objects_count == sender.objects_count("face")


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into shared layout as user with one company")
@pytest.mark.usefixtures('teardown_delete_layouts')
@pytest.mark.usefixtures('remove_other_companies')
def test_login_with_one_company_to_shared_layout(metapix, client, another_driver, sender):
    if len(get_available_companies(client)) != 1:
        raise PreconditionException(f'{client} has to have only one company')
    sender.check_min_objects_count({"face": 2})
    widget = metapix.dashboard.open_widget_builder().\
        create_value_widget(object_type="face")

    login_page = metapix.layout.share(another_driver, return_page=LoginPage)
    shared_layout = login_page.login(
        ignore_choosing_company=False,
        choose_default_company=False,
        return_page=DashboardPage,
    )
    assert shared_layout.widgets_titles == [widget.title]


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into metapix as user with several companies")
def test_login_with_multiple_companies_to_dashboard(login_page, second_company, driver):
    metapix = login_page.login(company_name=second_company.name)
    avatar_menu = metapix.open_avatar_menu()
    assert avatar_menu.company_name == get_company_title(driver)


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into shared widget as user with several companies")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1453')
@pytest.mark.usefixtures('second_company')
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_login_with_multiple_companies_to_shared_widget(metapix, client, another_driver, sender):
    sender.check_min_objects_count({"face": 2})
    widget = create_any_chart(metapix.dashboard, 'face')
    login_page = widget.share(another_driver, return_page=LoginPage)
    shared_widget = login_page.login(
        ignore_choosing_company=True,
        choose_default_company=False,
        return_page=widget_class_shared[widget.type],
    )
    assert shared_widget.objects_count == sender.objects_count("face")


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login into shared layout as user with several companies")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1453')
@pytest.mark.usefixtures('second_company')
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_login_with_multiple_companies_to_shared_layout(metapix, client, another_driver, sender):
    sender.check_min_objects_count({"face": 2})
    widget = create_any_widget(metapix.dashboard, 'face')
    login_page = metapix.layout.share(another_driver, return_page=LoginPage)
    shared_layout = login_page.login(
        ignore_choosing_company=True,
        choose_default_company=False,
        return_page=DashboardPage,
    )

    assert shared_layout.widgets_titles == [widget.title]


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/775")
@allure.title("Password ico in login page work correctly")
def test_login_page_has_password_ico(login_page):
    check_show_password_ico(login_page.password)


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("New company has no objects")
def test_new_company_has_no_objects(metapix, sender, second_company):
    sender.check_min_objects_count({"person": 1, "face": 1, "vehicle": 1}, timeslice=None)
    # TODO: it is possible to use another company instead of creating a new company each time?
    metapix.logout().\
        login(company_name=second_company.name)
    delete_all_cameras_for_client(metapix.driver.client)

    assert metapix.open_device_tree().cameras_schema == NO_CAMERAS
    assert metapix.search_count('face', ignore_no_data=True) == 0


@allure.epic('Frontend')
@allure.suite('Authorization')
@allure.title('It is possible to reset password')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1493')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1457')
@pytest.mark.usefixtures('teardown_restore_default_password')
@pytest.mark.parametrize('new_password', ['Double!3'])
def test_reset_password(metapix: RootPage, inbox: Inbox, new_password: str):
    with allure.step('Open "Send code" dialog by clicking button "Reset code"'):
        send_code_dialog = metapix.logout().reset_code()
        check_email_validation(send_code_dialog.input_email)

    with allure.step('Send confirmation code via email and open "Change Password" dialog'):
        change_password_dialog = send_code_dialog.send_code(inbox.email)
        check_input_is_disabled(change_password_dialog.input_email)
        check_input_validation(
            change_password_dialog.input_confirmatin_code,
            ['123456'],
            ['abcabc', '1234', ''],
        )
        check_password_validation(change_password_dialog.input_password)
        check_show_password_ico(change_password_dialog.input_password)

    with allure.step('Get confirmation code and set a new password'):
        confirmation_code = inbox.get_confirmation_code()
        login_page = change_password_dialog.change_password(
            confirmation_code, new_password)

    with allure.step('Check it is possible to login with new password'):
        login_page.login(email=inbox.email, password=new_password)


@allure.epic('Frontend')
@allure.suite('Token')
@allure.title('Check expired access token makes user to login (if frontend did not manage to refresh token)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1469')
@pytest.mark.parametrize('validity_time_minutes', [5])
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
@pytest.mark.usefixtures('second_company')  # for https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1469 check
def test_expired_access_token_causes_login_if_refresh_token_failed(
        metapix: RootPage,
        temporary_change_access_token_validity: Callable[[int, str], None],
        validity_time_minutes: int):
    '''
    FYI:
      https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/624
      https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1722966128774209
    '''

    def do_not_allow_to_refresh_access_token(request: Request):
        if request.path.endswith('/auth/refresh-token/'):
            log.warning(f'Abort {request.path}')
            request.abort()

    with allure.step('Change access token validity time and obtain a new token (via relogin)'):
        temporary_change_access_token_validity(value=validity_time_minutes, units='minutes')

    with allure.step('Wait until token expired. Do not allow frontend to refresh token'):
        metapix.driver.request_interceptor = do_not_allow_to_refresh_access_token
        access_token = get_access_token(metapix.driver)
        seconds_to_expire = get_time_to_expire(decode_token(access_token)['exp'])
        time.sleep(seconds_to_expire+10)

    with allure.step(f'Wait for {validity_time_minutes} minutes'):
        time.sleep(validity_time_minutes*60 + 5)
    assert is_element_exist(lambda: LoginPage(driver=metapix.driver))

    with allure.step('Make sure login page appeared'):
        assert is_element_exist(lambda: LoginPage(driver=metapix.driver))

    with allure.step('It is possible to log in after token expired'):
        login_page = LoginPage(driver=metapix.driver)
        login_page.login()


@allure.epic('Frontend')
@allure.suite('Token')
@allure.title('Check frontend refreshes token if it is about to expire')
@pytest.mark.parametrize('validity_time_minutes,delay_seconds', [(5, 10)])
def test_access_token_refreshes(
        metapix: RootPage,
        temporary_change_access_token_validity: Callable[[int, str], None],
        validity_time_minutes: int,
        delay_seconds: int,
):
    '''
    FYI:
      https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/624
      https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1722966128774209
    '''

    with allure.step('Change access token validity time and obtain a new token (via relogin)'):
        temporary_change_access_token_validity(value=validity_time_minutes, units='minutes')

    with allure.step(f'Wait for {delay_seconds} till access token is refreshed'):
        access_token = get_access_token(metapix.driver)
        time.sleep(delay_seconds)
        seconds_to_expire = get_time_to_expire(decode_token(access_token)['exp'])

    with allure.step('Make sure a new token has been obtained'):
        new_token = get_access_token(metapix.driver)
        assert new_token != access_token
        assert get_time_to_expire(decode_token(new_token)['exp']) > seconds_to_expire

    with allure.step('Make sure login dialog does not emerge'):
        time.sleep(validity_time_minutes * 60)
        assert not is_element_exist(lambda: LoginPage(driver=metapix.driver))


@allure.epic('Frontend')
@allure.suite('Authorization')
@allure.title('Check there is error when user does not exist')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1461')
@pytest.mark.parametrize('fake_email', [EmailType('fakeuser5231509235@uuuisd.op')])
def test_error_when_user_not_exist(
        login_page: LoginPage, fake_email: EmailType, default_pwd: str):
    login_page.submit_data(fake_email, default_pwd, wait_disappeared=False)
    login_page.assert_tooltip("Error: Specified user doesn't exist")


@allure.epic('Frontend')
@allure.suite('Authorization')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1517')
@allure.title('Check there is no interface deadlock if user did not select company')
@pytest.mark.usefixtures('second_company')
def test_open_root_in_case_user_did_not_select_company(
        another_driver: CustomWebDriver):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03L8340TBJ/p1723092803948819 '''
    # lets use another driver to keep main driver unspoiled
    auth_user_in_browser(
        another_driver,
        ignore_choosing_company=True,
        return_page=SwitchSystemDialog)
    with pytest.raises(PageDidNotLoaded):
        RootPage(driver=another_driver, open_page=True)
    assert is_element_exist(lambda: LoginPage(driver=another_driver))


@allure.epic('Frontend')
@allure.suite('Authorization')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1487')
@allure.title('User do not have to see the dashboard from the previous company')
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_dashboard_from_another_company_is_not_available(
        metapix: RootPage, second_company: CompanyInfoData):
    create_any_widget(metapix.dashboard)
    metapix.switch_company(). \
        select_by_name(second_company.name)
    assert metapix.dashboard.widgets_titles == []
