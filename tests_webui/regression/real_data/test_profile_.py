import allure
import pytest
import logging

from tools import PreconditionException
from tools.license_server import get_not_activated_licenses
from tools.licenses import activate_license
from tools.licenses import get_activated_licenses
from tools.webdriver import do_not_request_deleted_companies

from pages.root import RootPage

from tests_webui.regression import check_pagination

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Check pagination in 'List of users' table")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/113")
def test_profile_users_pagination(metapix, client):
    check_pagination(
        metapix.open_settings().open_users(client),
        ["email"],
    )


@allure.id('886')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('Pagination on the List of Companies page works correctly')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/193')
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
def test_list_of_companies_pagination(metapix: RootPage):
    metapix.driver.request_interceptor = do_not_request_deleted_companies
    check_pagination(
        metapix.open_settings().open_companies(),
        ["name", "email"],
    )


@pytest.fixture(scope='function')
def prepare_licenses_for_pagination_test(client, lic_server_admin):
    with allure.step(f'Prepare {client.user} for license pagination test'):
        log.info(f'Prepare {client.user} for license pagination test')
        activated_licenses = get_activated_licenses(client)
        available_licenses = get_not_activated_licenses(lic_server_admin)
        required_amount = 15 - len(activated_licenses)
        if required_amount > 0:
            if len(available_licenses) < required_amount:
                raise PreconditionException(f'Not enough licenses for user {client.user}')
            for license_ in available_licenses[:required_amount]:
                activate_license(client, license_.key)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Pagination on licenses page works correctly')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1428')
@pytest.mark.usefixtures('prepare_licenses_for_pagination_test')
def test_license_page_pagination(metapix):
    licenses_page = metapix.open_settings().open_licenses()
    check_pagination(licenses_page, ['key'])
