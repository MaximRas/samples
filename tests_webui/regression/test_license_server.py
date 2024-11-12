import uuid
import logging

import allure
import pytest

from selenium.common.exceptions import JavascriptException
from selenium.common.exceptions import WebDriverException

from tools.license_server import LicenseServerAPI
from tools.local_storage import LocalStorage
from tools.steps import check_company_name_validation
from tools.webdriver import create_webdriver
from tools.webdriver import get_main_js_workaround

from pages.base_page import ElementStillExistsException
from pages.license_server.login import LoginPage

from tests_webui.regression import check_pagination

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@pytest.fixture(scope='module')
def cameras():
    pass


@pytest.fixture(scope="function", autouse=True)
def teardown_local_storage(driver):
    yield
    with allure.step('Local Storage: clear all'):
        try:
            LocalStorage(driver).clear()
        except (JavascriptException, WebDriverException) as exc:
            log.error(f'Exception during clearing local storage: {exc}')


@pytest.fixture(scope='module')
def driver(session_options):
    driver = create_webdriver(session_options)
    yield driver
    driver.quit()


@pytest.fixture(scope="module")
def client(verified_client):
    return verified_client


@pytest.fixture(scope="function")
def login_page(driver, license_server_data):
    # TODO: does license server uses ReactJS and is it affected by the issue?
    get_main_js_workaround(driver, license_server_data['web_url'])
    return LoginPage(driver=driver)


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title("Authorization via admin works correct")
def test_lic_server_auth_admin(login_page, license_server_data, default_pwd):
    login_page.login(email=license_server_data["admin"], password=default_pwd)


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title("Authorization via integrator works correct")
def test_lic_server_auth_integrator(login_page, license_server_data, default_pwd):
    login_page.login(email=license_server_data["integrator"], password=default_pwd)


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title("Authorization via end user works correct")
def test_lic_server_auth_other_user(login_page, client):
    with pytest.raises(ElementStillExistsException):
        # ElementStillExistsException is being raised during `LoginPage.wait_disappeared`
        login_page.login(
            email=client.user.email,
            password=client.user.current_password,
        )


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title("Logout work correct")
def test_lic_server_logout(login_page, license_server_data, default_pwd):
    root_page = login_page.login(
        email=license_server_data["integrator"],
        password=default_pwd,
    )
    login_page = root_page.logout()
    assert login_page.parsed_url.path == LoginPage.path


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title("It should be possible reset password for logged user")
def test_lic_server_reset_password(login_page, license_server_data, default_pwd):
    login_page. \
        reset_password(license_server_data["integrator"], default_pwd). \
        login(email=license_server_data["integrator"], password=default_pwd)


@allure.epic("License manager")
@allure.suite("Licenses List")
@allure.title("Reseller can generate license by {user_type}")
@pytest.mark.parametrize(
    'days,channels,user_type',
    [
        (25, 12, 'integrator'),
        (40, 15, 'admin'),
    ],
    ids=['integrator', 'admin'],
)
def test_generate_license(login_page, license_server_data, default_pwd, days, channels, user_type):
    # TODO need reseller generator method
    licenses = login_page.login(
        email=license_server_data[user_type], password=default_pwd). \
        licenses
    license_key = licenses.generate_license(days=days, channels=channels)

    client = LicenseServerAPI(license_server_data['api_url'], license_server_data[user_type])
    license_info = client.get_license_by_id(license_key)
    assert license_info.key == license_key
    # assert license_info['company_name'] is None
    # assert license_info['company_owner_first_name'] is None
    # assert license_info['installation_name'] is None


@allure.epic("License manager")
@allure.suite("Licenses List")
@allure.title("Admin can see all licenses")
@pytest.mark.parametrize('days, channels', [(5, 6)])
def test_admin_sees_license_which_was_created_by_integrator(login_page, license_server_data, default_pwd, days, channels):
    admin_client = LicenseServerAPI(license_server_data["api_url"], license_server_data["admin"])
    amount_before = admin_client.amount

    with allure.step('Generate a license on behalf of integrator'):
        licenses = login_page.login(
            email=license_server_data["integrator"], password=default_pwd). \
            licenses
        licenses.generate_license(days=days, channels=channels)

    with allure.step('Check admin sees a new license'):
        assert amount_before + 1 == admin_client.amount


@allure.epic("License manager")
@allure.suite("Licenses List")
@allure.title("Pagination works on license page")
def test_pagination_license_server(login_page, license_server_data, default_pwd):
    check_pagination(
        login_page.login(
            email=license_server_data["admin"],
            password=default_pwd).
        licenses.license_table,
        fields=['key'],
    )


@allure.epic("License manager")
@allure.suite("Authorization")
@allure.title('Company name input field validation (license server)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/license-server/web-app/-/issues/11')
def test_lic_server_company_name_validation(login_page, license_server_data, default_pwd):
    # TODO: refactoring is required (get rid of calling of LicenseServerRootPage)
    root_page = login_page.login(
        email=license_server_data['admin'],
        password=default_pwd,
    )
    add_integrator_dialog = root_page. \
        open_integrators_list(). \
        open_add_new_integrator_dialog()
    check_company_name_validation(add_integrator_dialog.input_company_name)


@allure.epic("License manager")
@allure.suite("License List")
@allure.title('Field contract ID should work as expected')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1337')
@pytest.mark.parametrize('contractid', [str(uuid.uuid4()), None], ids=['with_contract_id', 'without_contract_id'])
def test_contract_id_field(login_page: LoginPage, license_server_data: str, default_pwd: str, contractid: str):
    with allure.step("Login to license server"):
        license_table = login_page.login(
            email=license_server_data['admin'],
            password=default_pwd,
        ).licenses
    with allure.step(f"Create license with contract id {contractid}"):
        licence_key = license_table.generate_license(3, 5, contractid)

    with allure.step("Get created license info from API"):
        client = LicenseServerAPI(license_server_data['api_url'], license_server_data['admin'])
        license_info = client.get_license_by_id(licence_key)
    with allure.step("Check than contract id is match with created license"):
        assert license_info.contract_id == contractid
