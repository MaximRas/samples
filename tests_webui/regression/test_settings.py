from copy import deepcopy
from typing import Any
from typing import Mapping
import json
import logging
import time
import uuid

import allure
import pytest
from seleniumwire.request import Request
from seleniumwire.request import Response

import consts
from tools import PreconditionException
from tools import check_images_are_equal
from tools import check_images_are_not_equal
from tools import config
from tools import fix_page_path
from tools import run_test
from tools import send_value_to_test
from tools import sort_list_by_dict_key
from tools.cameras import disable_camera
from tools.cameras import get_camera_by_name
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.licenses import get_activated_licenses
from tools.search import search_api_v2
from tools.steps import check_company_name_validation
from tools.steps import check_email_validation
from tools.steps import check_input_is_disabled
from tools.steps import check_name_validation
from tools.steps import check_password_validation
from tools.steps import create_widget_api
from tools.steps import find_in_all_pages
from tools.time_tools import Ago
from tools.time_tools import DATETIME_FORMAT_DEFAULT
from tools.time_tools import DATETIME_FORMAT_DMY_DASH_12H
from tools.time_tools import TimeZone
from tools.time_tools import date_to_str
from tools.time_tools import now_pst
from tools.time_tools import timedelta_hours
from tools.tokens import create_token
from tools.types import ApiUserRole
from tools.types import DateTimeFormatType
from tools.types import EmailType
from tools.types import XPathType
from tools.users import CompanyDoesNotExistException
from tools.users import add_new_company
from tools.users import auth_euc_admin_in_browser
from tools.users import auth_euc_regular_user_in_browser
from tools.users import auth_ic_admin_in_browser
from tools.users import auth_ic_regular_user_in_browser
from tools.users import auth_spc_admin_in_browser
from tools.users import auth_spc_regular_user_in_browser
from tools.users import auth_user_in_browser
from tools.users import change_user_name
from tools.users import filter_companies
from tools.users import generate_company_name
from tools.users import get_active_user
from tools.users import get_company_by_name
from tools.users import get_descendant_companies
from tools.users import get_random_name
from tools.users import get_second_user_client
from tools.users import get_second_user
from tools.users import get_user_without_company
from tools.users import register_user
from tools.watchlists import add_predicates
from tools.watchlists import create_face_predicates
from tools.watchlists import create_watchlist
from tools.webdriver import CustomWebDriver
from tools.webdriver import do_not_request_deleted_companies
from tools.webdriver import get_body

from pages.base_page import BasePage
from pages.input_base import has_clear_button
from pages.base_page import is_element_exist
from pages.dialog import Dialog
from pages.dropdown import DropdownExpandException
from pages.ico_dialog import IcoDialog
from pages.login import LoginPage
from pages.navigation import BaseContentTable
from pages.registration import complete_registration
from pages.registration import open_registration_form
from pages.root import RootPage
from pages.settings import dialog_add_company
from pages.settings.companies import CompaniesTable
from pages.settings.companies import UICompanyType
from pages.settings.companies import UIUserRole
from pages.settings.users import NoDeleteButtonException
from pages.settings.users import UsersPage
from pages.switch_company import CURRENT_COMPANY
from pages.switch_company import merge_recently_visited_and_favorite
from pages.switch_company import move_group_to_favorites

from tests_webui.regression import get_input_labels
from tests_webui.regression import get_button_labels
from tests_webui.regression import check_show_password_ico
from tests_webui.regression import check_submit_button_active_if_all_fields_filled
from tests_webui.regression import check_datetime_format

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)

HELSINKI_TIMEZONE = TimeZone('+03:00 Europe/Helsinki')


def get_total_channels(client: ApiClient) -> int:
    return sum(lic.cameras_count for lic in get_activated_licenses(client) if lic.is_expired is False)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to add new users with different roles")
@pytest.mark.parametrize('role', [UIUserRole.REGULAR])
def test_add_new_regular_user_ui(metapix, client, inbox, another_driver, role):
    def check_schema(current, before, new_entry):
        assert sort_list_by_dict_key(current, key_to_sort='email') == \
            sort_list_by_dict_key(before + [new_entry], key_to_sort='email')

    first_name, last_name = get_random_name('First'), get_random_name('Last')
    users_page = metapix.open_settings(). \
        open_users(client)
    users_page.pages.set_value(consts.PAGINATION_MAX)
    inbox = inbox.create_new()
    schema_before = users_page.schema

    with allure.step('Check users schema (registration was not completed)'):
        users_page.add_user(email=inbox.email, role=role)
        # FYI: (why email is in lower case?) client/metapix-frontend-app/-/issues/705
        check_schema(
            users_page.schema, schema_before,
            {
                'name': 'Invited User',
                'email': inbox.email,
                'role': role.lower().capitalize(),  # "Regular User -> "Regular user"
            }
        )

    with allure.step('Complete registration and check users schema'):
        complete_registration(inbox, another_driver, first_name=first_name, last_name=last_name)
        users_page.refresh()
        check_schema(
            users_page.schema,
            schema_before,
            {
                'name': f'{first_name} {last_name}',
                'email': inbox.email,
                'role': role.lower().capitalize(),  # "Regular User -> "Regular user"
            },
        )
    # TODO: add teardown (remove added users)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to log out")
def test_log_out(metapix):
    login_page = metapix.logout()
    assert login_page.parsed_url.path == fix_page_path(LoginPage.path)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to change password")
@pytest.mark.usefixtures("teardown_restore_default_password")
def test_change_password(metapix, client):
    new_password = client.user.current_password + '_new'
    user_settings = metapix.open_user_settings()
    user_settings. \
        change_password(client.user.current_password, new_password)
    user_settings.close()
    metapix.logout(). \
        login(password=new_password)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to add/delete user photo")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/112")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/147")
@pytest.mark.usefixtures("teardown_delete_user_photo")
def test_add_delete_user_photo(metapix, sender):
    user_settings = metapix.open_user_settings()

    with allure.step('It is possible to add user photo'):
        image_no_avatar = user_settings.user_image.screenshot_as_png
        user_settings. \
            open_upload_photo_dialog(sender.base_images_dir / 'face' / 'with-beard.jpg'). \
            confirm()
        check_images_are_not_equal(user_settings.user_image.screenshot_as_png, image_no_avatar)
        image_avatar_with_beard = user_settings.user_image.screenshot_as_png

    with allure.step('It is possible to replace user photo'):
        user_settings. \
            open_replace_photo_dialog(sender.base_images_dir / 'face' / 'with-glasses.jpg'). \
            confirm()
        check_images_are_not_equal(user_settings.user_image.screenshot_as_png, image_no_avatar)
        check_images_are_not_equal(user_settings.user_image.screenshot_as_png, image_avatar_with_beard)

        with allure.step('It is possible to remove user photo'):
            user_settings.open_remove_avatar_dialog().confirm()
            check_images_are_equal(user_settings.user_image.screenshot_as_png, image_no_avatar)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("License Table. License does not exist or already activated")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1454')
def test_enter_invalid_uuid_license_key(metapix):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1676472679040769 '''
    licenses_page = metapix.open_settings(). \
        open_licenses()
    invalid_uuid = str(uuid.uuid4())
    license_dialog = licenses_page.open_activate_new_license_dialog()
    license_dialog.set_value(invalid_uuid)
    assert license_dialog.button_confirm.is_active() is True
    license_dialog.button_confirm.click()
    metapix.assert_tooltip("Error: License doesn't exist")

    with allure.step('Check the dialog has disappeared'):
        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1047
        license_dialog.wait_disappeared()


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("License Table. Invalid format key")
def test_enter_invalid_format_key(metapix):
    licenses_page = metapix.open_settings(). \
        open_licenses()
    invalid_key = 'invalid_format_key123!@#'
    license_dialog = licenses_page.open_activate_new_license_dialog()
    license_dialog.set_value(invalid_key)
    assert 'Invalid license key' in license_dialog.input_value.tooltip
    assert license_dialog.button_confirm.is_active() is False


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to change last and first name")
@pytest.mark.usefixtures('teardown_restore_name')
def test_change_user_name_last_name(metapix):
    user_settings = metapix.open_user_settings()

    user_settings.change_name(first_name='Vladimir', last_name='Lenin')
    user_settings.close()

    assert metapix.open_avatar_menu().user_name == 'Vladimir Lenin'

    metapix.refresh()
    assert metapix.open_avatar_menu().user_name == 'Vladimir Lenin'


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Password length must be in range 8-99")
def test_password_length(metapix, default_pwd):
    """
    Add maxlenght constraint to password field. User should not be able to enter password more than 99 symbols.
    https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/462
    """
    user_settings = metapix.open_user_settings()

    user_settings.input_old_password.type_text(default_pwd)   # to be able to check "Save" button state
    check_password_validation(
        user_settings.input_new_password,
        button=user_settings.button_save_password,
    )


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Frontend user name validation (Settings -> Users -> Change Name")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/925')
def test_users_name_validation_change_name(metapix, client):
    user_settings = metapix.open_user_settings()

    check_name_validation(
        user_settings.input_first_name,
        button=user_settings.button_save_name,
    )
    user_settings.input_first_name.type_text(client.user.first_name)  # restore first name

    check_name_validation(
        user_settings.input_last_name,
        button=user_settings.button_save_name,
    )


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/475")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/762")
@allure.title("Error tooltips of input fields must not be capitalized")
def test_invalid_input_tooltips_capitalized(metapix, client):
    def is_not_capitalized(password):
        assert password is not None, "No tooltip"
        for word in password.tooltip.split(' '):
            if word[0].isalpha() and word[0].islower():
                return True
        return False

    user_settings = metapix.open_user_settings()
    assert is_not_capitalized(user_settings.input_first_name.clear_with_keyboard())
    assert is_not_capitalized(user_settings.input_last_name.clear_with_keyboard())
    assert is_not_capitalized(user_settings.input_new_password.clear_with_keyboard().type_text("string"))
    assert is_not_capitalized(user_settings.input_old_password.clear_with_keyboard().type_text("string"))


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/762")
@allure.title("Equal tooltips in 'old password' and 'new password' inputs")
def test_invalid_password_messages_are_same(metapix, default_pwd):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1676559256297529 '''
    user_settings = metapix.open_user_settings()

    first_name_invalid_msg = user_settings.input_old_password. \
        type_text(consts.INVALID_PASSWORD, clear_with_keyboard=True).tooltip

    second_name_invalid_msg = user_settings.input_new_password. \
        type_text(consts.INVALID_PASSWORD, clear_with_keyboard=True).tooltip

    assert first_name_invalid_msg == second_name_invalid_msg


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Cancel deleting user from user list")
def test_cancel_delete_user(metapix, client, default_pwd, inbox):
    users_page = metapix.open_settings(). \
        open_users(client)
    users_page.pages.set_value(consts.PAGINATION_MAX)
    user_email = users_page.add_user(
        email=inbox.create_new().email,
        role=UIUserRole.REGULAR,
    )
    user = users_page.get_user(user_email)
    user.open_delete_dialog().cancel()
    assert is_element_exist(lambda: user._element) is True


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Cancel deleting user picture")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/147")
@pytest.mark.usefixtures("teardown_delete_user_photo")
def test_cancel_delete_photo(metapix, sender):
    user_settings = metapix.open_user_settings()

    user_settings. \
        open_upload_photo_dialog(sender.base_images_dir / 'face' / 'with-beard.jpg'). \
        confirm()
    image_avatar_with_beard = user_settings.user_image.screenshot_as_png

    user_settings. \
        open_remove_avatar_dialog(). \
        cancel()
    check_images_are_equal(user_settings.user_image.screenshot_as_png, image_avatar_with_beard)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Check warning for users in copy token dialog")
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_copy_token_warning(metapix):
    tokens_page = metapix.open_settings(). \
        open_tokens()
    generate_token_dialog = tokens_page.open_add_token_dialog()
    generate_token_dialog. \
        set_value('New token'). \
        confirm()
    assert tokens_page.copy_token_dialog.message == 'Warning\n' \
        'Please note that if you do not copy the token value before ' \
        'closing the pop-up, you will need to generate a new one'


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Check message in delete token dialog")
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_delete_token_message(metapix, client):
    create_token(client, 'Token')
    token = metapix.open_settings(). \
        open_tokens(). \
        tokens.get('Token')

    delete_token_dialog = token.open_delete_dialog()
    assert delete_token_dialog.message == 'If you delete a Token used to connect '  \
        'Metapix Plugin with the Cloud, the solution will cease to detect objects, '\
        'resulting in a significant disruption to the overall system.'


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Generate and delete token")
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_generate_and_delete_token(metapix):
    tokens_page = metapix.open_settings(). \
        open_tokens()
    tokens_before = tokens_page.schema
    tokens_page.add_token("New Token")
    assert tokens_page.schema == [
        {"name": "New Token", "generated at": date_to_str(now_pst())},
    ]
    tokens_page.tokens[0].delete()
    assert tokens_page.schema == tokens_before


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Cancel deleting token")
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_cancel_deleting_token(metapix):
    tokens_page = metapix.open_settings(). \
        open_tokens()
    tokens_before = tokens_page.schema
    tokens_page.add_token("New Token")
    tokens_page.tokens[0].open_delete_dialog().cancel()
    assert tokens_page.schema == tokens_before + [
        {"name": "New Token", "generated at": date_to_str(now_pst())},
    ]


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.tag("bug")
@allure.title("User settingss -> change name dialog: text doesn't disappear in some time")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/652")
def test_refresh_token_request_does_not_reset_first_name(metapix):
    user_settings = metapix.open_user_settings()
    user_settings.input_first_name.type_text("Harry", clear_with_keyboard=True)
    user_settings.input_last_name.type_text("Potter", clear_with_keyboard=True)
    time.sleep(40)  # wait refresh token request. it is being sent every 30 sec
    assert user_settings.input_first_name.value == "Harry"
    assert user_settings.input_last_name.value == "Potter"


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/775')
@allure.title('Test in profile field has password ico')
def test_password_ico_in_profile_settings(metapix):
    user_settings = metapix.open_user_settings()
    check_show_password_ico(user_settings.input_old_password)
    check_show_password_ico(user_settings.input_new_password)


@allure.id('881')
@allure.title('The Cancel button in the Add New Company window works correctly')
@allure.epic("Frontend")
@allure.suite("Profile")
def test_cancel_create_new_company(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    table_of_companies_before = companies_page.schema
    companies_page.open_add_new_company(). \
        fill(
            name=generate_company_name(),
            type_=dialog_add_company.TYPE_EUC,
            email=client.user.email,
            address='SPB, Rubinstein',
        ). \
        cancel()

    assert companies_page.schema == table_of_companies_before


@allure.id('923')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('After creating company: validation on fields in "Add admin user" window')
def test_add_user_dialog_validation_after_creating_company(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    add_company_dialog.fill(
        name=generate_company_name(),
        type_=dialog_add_company.TYPE_EUC,
        email=client.user.email,
        address='SPB, Rubinstein',
    )
    add_user_dialog = add_company_dialog.confirm()
    check_email_validation(add_user_dialog.email)

    with allure.step('Check there is no surplus controls in "Add New User" dialog'):
        assert get_input_labels(add_user_dialog) == ('E-Mail', 'Role')
        assert get_button_labels(add_user_dialog) == ('SKIP', 'ADD')

    check_submit_button_active_if_all_fields_filled(
        add_user_dialog.button_confirm,
        [(add_user_dialog.email, client.user.email)],
    )


@allure.id('918')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] Fill all fields -> all values displayed in the Companies List table')
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
def test_companies_all_values_are_displayed_after_adding(metapix, driver):
    auth_ic_admin_in_browser(driver)
    metapix.driver.request_interceptor = do_not_request_deleted_companies
    companies_page = metapix.open_settings(). \
        open_companies()
    new_company_name = generate_company_name()
    companies_page.open_add_new_company(). \
        add(
            name=new_company_name,
            type_=dialog_add_company.TYPE_EUC,
            email='vbelyaev@metapix.ai',
            address='SPB, Rubinstein',
        ). \
        skip()  # skip "Add new user"
    assert find_in_all_pages(companies_page, {
        'name': new_company_name,
        'role': UIUserRole.ADMIN,
        'type': UICompanyType.EUC,
        'email': EmailType('vbelyaev@metapix.ai'),
        'address': 'SPB, Rubinstein',
    })


@allure.id('919')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] Fill only required fields -> only filled values displayed in the Companies List table, other values is empty')
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
def test_companies_fill_only_required_fields(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    driver.request_interceptor = do_not_request_deleted_companies
    companies_page = metapix.open_settings(). \
        open_companies()
    new_company_name = generate_company_name()
    add_company_dialog = companies_page.open_add_new_company()
    # TODO: check tooltip 'Field cannot be empty'
    add_company_dialog.fill(
        name=new_company_name,
        type_=dialog_add_company.TYPE_EUC,
        email=client.user.email,
        address='SPB, Rubinstein',
    )
    add_company_dialog.confirm(). \
        skip()  # skip "Add new user"
    assert find_in_all_pages(companies_page, {
        'name': new_company_name,
        'role': UIUserRole.ADMIN,
        'type': UICompanyType.EUC,
        'address': 'SPB, Rubinstein',
        'email': client.user.email,
    })


@allure.id('931')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('List of companies table has header "List of companies"')
def test_companies_table_header(metapix):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1704998077035569 '''
    companies_page = metapix.open_settings(). \
        open_companies()
    assert companies_page.table_name == 'List of Companies'


@allure.id('925')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] If logged by admin from IC: it`s possible to add only End User Company (dropdown disabled)')
def test_IC_it_is_possible_to_add_only_EUC(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    add_company_dialog = metapix.open_settings(). \
        open_companies(). \
        open_add_new_company()
    add_company_dialog.company_type.expand()
    assert add_company_dialog.company_type.options == {dialog_add_company.TYPE_EUC}


@allure.id('880')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] If logged by admin from SPC: it`s possible to add Integrator and End User Company')
def test_SPC_it_is_possible_to_add_EUC_IC(metapix, driver):
    auth_spc_admin_in_browser(driver)
    add_company_dialog = metapix.open_settings(). \
        open_companies(). \
        open_add_new_company()
    add_company_dialog.company_type.expand()
    assert add_company_dialog.company_type.options == \
        {dialog_add_company.TYPE_IC, dialog_add_company.TYPE_EUC}


@allure.id('920')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] Submit button is disabled until the required parameters are filled in (company type and name)')
def test_add_new_company_submit_button_is_disabled(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    new_company_name = generate_company_name()
    add_company_dialog = companies_page.open_add_new_company()

    check_submit_button_active_if_all_fields_filled(
        add_company_dialog.button_confirm,
        (
            (add_company_dialog.input_company_name, new_company_name),
            (add_company_dialog.company_type, dialog_add_company.TYPE_EUC),
            (add_company_dialog.input_contact_email, client.user.email),
            (add_company_dialog.input_contact_address, 'SPB, Rubinstein'),
        ),
    )


@allure.id('924')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('After creating company: Cancel button in "Add admin user" works correctly, returning to Companies List page')
def test_cancel_button_after_creating_company(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    add_company_dialog.fill(
        name=generate_company_name(),
        type_=dialog_add_company.TYPE_EUC,
        email=client.user.email,
        address='SPB, Rubinstein',
    )
    add_new_user_dialog = add_company_dialog.confirm()
    assert add_new_user_dialog.caption == 'Success\nYou have already been added as an Administrator ' \
        'to the new company. If you want, you can add another Administrator'

    add_new_user_dialog.skip()
    # check we skill located on 'List of Companies' page
    assert companies_page.table_name == 'List of Companies'


@allure.id('922')
@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('After creating company: window "Add admin user" is appear. Role dropdown is disabled and Administrator is selected. Pop-up "Successful creating company" is appeared')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1627')
def test_admin_role_after_creating_company(metapix, driver, client):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    add_company_dialog.fill(
        name=generate_company_name(),
        type_=dialog_add_company.TYPE_EUC,
        email=client.user.email,
        address='SPB, Rubinstein',
    )
    add_new_user_dialog = add_company_dialog.confirm()
    assert add_new_user_dialog.role.value == UIUserRole.ADMIN
    with pytest.raises(DropdownExpandException):
        add_new_user_dialog.role.expand()


@allure.id('926')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('[Add new company] If logged by admin from EUC: it`s NOT possible to add company')
def test_EUC_admin_has_no_add_company_button(metapix):
    '''
    The button isn't available for EUC admin
    Default client is EUC admin so we don't need any extra moves
    '''
    companies_page = metapix.open_settings(). \
        open_companies()
    assert is_element_exist(lambda: companies_page.button_add_new_company) is False


@allure.id('884')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('The Add New Company button is NOT available for a user with the Regular User role')
@pytest.mark.parametrize(
    "auth_method",
    [
        auth_euc_regular_user_in_browser,
        pytest.param(
            auth_ic_regular_user_in_browser,
            marks=allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/837'),
        ),
        pytest.param(
            auth_spc_regular_user_in_browser,
            marks=allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/837'),
        ),
    ],
    ids=['EUC regular', 'IC regular', 'SPC regular']
)
def test_add_new_company_button_is_not_available_for_regular_user(metapix, driver, auth_method):
    '''
    The buttons isn't available for any regular user
    IC, SPC, EUC: Regular user doesn't have 'Add new company' button
    '''
    auth_method(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    assert is_element_exist(lambda: companies_page.button_add_new_company) is False


@allure.id('887')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('The Companies section displays only those companies that are subsidiaries of the user\'s current company.')
def test_list_of_companies_has_only_subsidaries_of_the_users_current_company(metapix, client):
    # TODO: how many descendant companies should this user have?
    companies_page = metapix.open_settings(). \
        open_companies()
    companies_page.pages.set_value(consts.PAGINATION_MAX)
    expected_companies = [c.name for c in get_descendant_companies(client)]
    assert sorted(expected_companies) == sorted([c['name'] for c in companies_page.schema])


@allure.id('870')
@allure.epic("Frontend")
@allure.suite("Profile")
@pytest.mark.parametrize(
    "auth_method",
    [
        auth_euc_admin_in_browser,
        auth_ic_admin_in_browser,
        auth_spc_admin_in_browser,
    ],
    ids=['EUC admin', 'IC admin', 'SPC admin']
)
@allure.title('The [users] button is available for a user with the Administrator role. Clicking takes you to the Users page')
def test_users_button_available_for_admin(metapix, driver, auth_method):
    auth_method(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    companies_page.pages.set_value(consts.PAGINATION_MAX)
    company = companies_page.get(driver.client.company.name)
    users_page = company.open_users()
    assert users_page.table_name == f"Users List in '{driver.client.company.name}'"


@allure.id('873')
@allure.epic("Frontend")
@allure.suite("Profile")
@pytest.mark.parametrize(
    "auth_method",
    [
        auth_euc_regular_user_in_browser,
        auth_ic_regular_user_in_browser,
        auth_spc_regular_user_in_browser,
    ],
    ids=['EUC regular', 'IC regular', 'SPC regular']
)
@allure.title('The [users] button is available for a user with the Regular User role. Clicking takes you to the Users page')
def test_users_button_available_for_regular_user(metapix, driver, auth_method):
    auth_method(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    companies_page.pages.set_value(consts.PAGINATION_MAX)
    users_page = companies_page.get(driver.client.company.name).open_users()
    assert users_page.table_name == f"Users List in '{driver.client.company.name}'"


@allure.id('882')
@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('Validation of fields Company Name, Contact e-mail, Contact address')
def test_validation_add_new_company(metapix, driver):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    check_email_validation(add_company_dialog.input_contact_email, allow_empty=True)
    # TODO: there is no validation for contact address. add_company_dialog.input_contact_address


def generate_help_menu(env):
    def build_menu(template, prefix=None, max_lines=None):
        new_menu = []
        for line_ix, template_line in enumerate(template):
            if prefix:
                template_line = f'{prefix} - {template_line}'
            new_menu.append(template_line)
            if max_lines and max_lines == line_ix + 1:
                break
        return new_menu

    template = [
        'Plugin and Gateway Installation',
        'Plugin Configuration Process',
        'Plugin and Gateway Upgrade',
        'Process on Watch List Management',
        'Frequently Asked Questions',
    ]

    if env == 'mymetapix':
        return build_menu(template, prefix='My Metapix')
    if env == 'sharpvue':
        return build_menu(template, prefix='Sharpvue', max_lines=1)
    return build_menu(template)


@allure.epic("Frontend")
@allure.suite("Help Page")
@allure.title("Testing help page menu")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/882')
def test_help_page_menu(metapix):
    help_page = metapix.open_help_page()
    assert help_page.schema == generate_help_menu(config.environment)
    assert help_page.content.startswith("Plugin And Gateway Installation")

    help_page.navigation[1].click()
    assert help_page.content.startswith("Plugin Configuration Process")


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/362')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/792')
@allure.title('Delete user and check the user has disappeared from the table. register user: {is_registration_required}')
@pytest.mark.parametrize(
    'is_registration_required', [
        pytest.param(
            False,
            marks=[
                allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1439'),
                allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1490'),
            ]
        ),
        True,
    ],
    ids=['invited_user', 'registered_user'],
)
def test_deleted_user_still_shown_in_users_list(metapix, client, inbox, is_registration_required):
    # TODO: consider using existing users
    def get_expected_schema(schema, inbox):
        schema = deepcopy(schema)
        for item in schema.copy():
            if EmailType(item['email']) == inbox.email:
                schema.remove(item)
                return schema
        raise RuntimeError(f'There is no user with email: {inbox.email}')

    users_page = metapix.open_settings(). \
        open_users(client)
    users_page.pages.set_value(consts.PAGINATION_MAX)
    new_inbox = inbox.create_new()
    users_page. \
        open_add_user_dialog(). \
        add_user(
            email=new_inbox.email,
            role=UIUserRole.REGULAR,
        )
    schema_before = users_page.schema
    if is_registration_required:
        register_user(client, new_inbox, get_random_name('First'), get_random_name('Last'))
        users_page.refresh()
    users_page.get_user(new_inbox.email).delete()
    assert users_page.schema == get_expected_schema(schema_before, new_inbox)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/383")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/755")
@allure.title("User should not be able to delete himself and users with same tier and abow")
def test_user_should_not_be_able_to_delete_himself(metapix, client):
    users_page = metapix.open_settings(). \
        open_users(client)
    with pytest.raises(NoDeleteButtonException):  # Check there is no 'delete' button for current user
        users_page.get_user(client.user.email).delete()


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.tag('bug')
@allure.title("Infinite loader when uploading wrong file format")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/871')
@pytest.mark.usefixtures("teardown_delete_user_photo")
def test_upload_unsupported_file(metapix, sender):
    user_settings = metapix.open_user_settings()

    user_settings. \
        open_upload_photo_dialog(sender.base_images_dir / 'face' / 'with-beard.jpg'). \
        confirm()
    assert is_element_exist(
        lambda: user_settings.
        open_replace_photo_dialog(
            sender.base_images_dir / 'invalid_image.jpg',
            wait_timeout=2)) is False
    metapix.assert_tooltip('Error: Unsupported file format')


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.tag('bug')
@allure.title("User should not be able to see list of users if he don't added to this company")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/143')
@pytest.mark.skip('Refactoring is required')
def test_SPC_can_inspect_company_only_if_he_belongs_to(metapix, driver):
    auth_spc_admin_in_browser(driver)
    companies = get_descendant_companies(driver.client)
    companies_page = metapix.open_settings(). \
        open_companies()
    companies_page.pages.set_value(consts.PAGINATION_MAX)
    companies_count_with_role = 0
    companies_count_without_role = 0

    for company_on_page in companies_page.companies:
        company = filter_companies(companies, company_on_page.name) or {}
        if company.role:
            with allure.step(f'Check {company_on_page} has "Users" button'):
                assert is_element_exist(lambda: company_on_page.button_users) is True
                companies_count_with_role += 1
        else:
            with allure.step(f'Check {company_on_page} does not have "Users" button'):
                assert is_element_exist(lambda: company_on_page.button_users) is False
                companies_count_without_role += 1

    # make sure we checked all scenarios
    assert companies_count_with_role > 0
    assert companies_count_without_role > 0


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.story("Switch Company")
@allure.title("Check the order of new company: companies table and 'choose company' dialog")
@pytest.mark.skip('Not implemented yet https://metapix-workspace.slack.com/archives/C03KBMWC146/p1683815365404569')
def test_new_company_order(metapix, client):
    companies_page = metapix.open_settings(). \
        open_companies()
    table_of_companies_before = companies_page.schema

    new_company = add_new_company(client)
    table_of_companies_before.append({"name": new_company.name, "role": "owner"})

    companies_page.refresh()
    assert companies_page.schema == table_of_companies_before

    switch_company_dialog = metapix.switch_company()
    assert switch_company_dialog.available_companies[0] == new_company.name


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.story("Switch Company")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/679")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/756")
@allure.title("New company appears in the 'Switch company' immediately after adding")
@pytest.mark.usefixtures("second_company")  # 'Switch Company' dialog isn't available if there are no companies to switch
def test_new_company_in_switch_company_dialog(metapix, client):
    new_company = add_new_company(client).name
    metapix.switch_company(). \
        select_by_name(new_company)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.story("Switch Company")
@allure.title("Search work correct in switch window")
def test_search_in_switch_window(metapix, second_company):
    company_name = second_company.name
    switch_window = metapix.switch_company()

    assert switch_window.search_name(company_name) == [company_name]
    assert switch_window.search_name(company_name.upper()) == [company_name]
    assert switch_window.search_name(company_name.lower()) == [company_name]


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Settings/licenses should have 'Licenses summary'")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1062')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1380')
@pytest.mark.usefixtures('teardown_enable_cameras')
def test_settings_licenses_summary_one_channel_is_disabled(metapix, client):
    disable_camera(client, get_camera_by_name(client, 'camera-4'))
    licenses_page = metapix.open_settings(). \
        open_licenses()

    channels_in_total = get_total_channels(client)
    assert licenses_page.licenses_summary == \
        'Licenses summary\n' \
        f'{channels_in_total} Channels in total\n' \
        '3 Channels currently in use'  # 4 cameras minus 1 disabled camera


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to close 'Choose company' dialog")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1081')
@pytest.mark.usefixtures("second_company")
def test_close_choose_company_dialog(metapix):
    # TODO: more scenarios
    choose_company_dialog = metapix.switch_company()
    choose_company_dialog.close()
    assert is_element_exist(lambda: choose_company_dialog) is False


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('"Change Timezone" dialog should display current timezone')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1188')
def test_settings_change_timezone_dialog_has_value(metapix, client):
    expected_timezone = get_active_user(client).timezone
    user_settings = metapix.open_user_settings()
    with allure.step('Check "Change Timeslice" dialog has the same value as auth-manager/v1/user had returned'):
        assert expected_timezone in user_settings.timezone


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('Test "Cancel" button in "Change Timezone" dialog')
@pytest.mark.usefixtures("teardown_restore_timezone")
@pytest.mark.parametrize('new_timezone', [HELSINKI_TIMEZONE])
def test_cancel_changing_timezone(metapix, new_timezone):
    user_settings = metapix.open_user_settings()
    old_timezone = user_settings.timezone
    assert old_timezone not in new_timezone  # self check

    user_settings.dropdown_timezone.select_option(new_timezone)
    user_settings.close()
    user_settings = metapix.open_user_settings()
    assert user_settings.timezone == old_timezone


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('Check Timezone dropdown does not have "Clear" button')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1189')
@pytest.mark.usefixtures("teardown_restore_timezone")
@pytest.mark.parametrize('new_timezone', [HELSINKI_TIMEZONE])
def test_timezone_does_not_have_clear_button(metapix, new_timezone):
    user_settings = metapix.open_user_settings()

    with allure.step('There is no "clear" button by default'):
        assert not has_clear_button(user_settings.dropdown_timezone)

    with allure.step('There is no "clear" button after selecting another timezone'):
        user_settings.dropdown_timezone.select_option(new_timezone)
        assert not has_clear_button(user_settings.dropdown_timezone)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Changing time zone should apply for all objects')
@pytest.mark.usefixtures('teardown_restore_timezone')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1488')
def test_changing_timezone_should_apply_for_all_objects(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    obj = search_api_v2(sender.client, 'face').get_first()
    datetime_before = metapix.open_object(obj.id).thumbnail.to_datetime()
    user_settings = metapix.open_user_settings()
    user_settings.change_time_settings(timezone=HELSINKI_TIMEZONE)
    user_settings.close()

    # difference between two timestamps should be equal to difference with two timezones
    # -00:00 America/Los_Angeles  and +02:00 Europe/Helsinki == difference 9/10 hours
    delta = datetime_before - metapix.open_object(obj.id).thumbnail.to_datetime()
    assert timedelta_hours(delta) in (9, 10)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1159')
@allure.title("Pagination persists after trying to add/delete gateway token")
@pytest.mark.usefixtures("teardown_delete_tokens")
def test_pagination_resets_after_addding_deleting_token(metapix, client):
    '''
    NB: The same behavior when it comes to license page
    '''
    create_token(client, 'Token to show table')
    tokens_page = metapix.open_settings(). \
        open_tokens()
    tokens_page.pages.set_value(200)
    tokens_page.add_token('Test token')
    assert tokens_page.pages.value == '200'

    tokens_page.tokens.get('Test token').delete()
    assert tokens_page.pages.value == '200'


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title('Company name input field validation (settings -> add new company)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/license-server/web-app/-/issues/11')
def test_settings_company_name_validation(metapix, driver):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    check_company_name_validation(add_company_dialog.input_company_name)


@allure.epic('Frontend')
@allure.suite('Profile')   # TODO: what suite????
@allure.title('Check it is possible to add company to favorite companies')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1278')
@pytest.mark.usefixtures('teardown_no_favorite_companies')
def test_favorite_company(metapix, second_company):
    choose_company_dialog = metapix.switch_company()
    schema = choose_company_dialog.schema

    with allure.step('It is possible to add company to "favorite companies"'):
        title, company = choose_company_dialog.get_company(second_company.name)
        company.make_favorite()
        assert merge_recently_visited_and_favorite(choose_company_dialog.schema) \
            == move_group_to_favorites(schema, title, second_company.name)

    with allure.step('Adding to "favorite companies" pesists after closing "Choose company" dialog'):
        choose_company_dialog.close()
        metapix.switch_company()
        assert merge_recently_visited_and_favorite(choose_company_dialog.schema) \
            == move_group_to_favorites(schema, title, second_company.name)

    with allure.step('It is possible to remove company from "favorite companies"'):
        _, company = choose_company_dialog.get_company(second_company.name)
        company.cancel_favorite()
        assert choose_company_dialog.schema == schema

    with allure.step('Removing to "favorite companies" pesists after closing "Choose company" dialog'):
        choose_company_dialog.close()
        metapix.switch_company()
        assert choose_company_dialog.schema == schema


@allure.epic('Frontend')
@allure.suite('Profilef')
@allure.title('Choose company dialog: searching company. Check that match part of company name is highlighted')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1274')
@pytest.mark.usefixtures('teardown_no_favorite_companies')
@pytest.mark.parametrize('query', ['Test'])
def test_choose_company_dialog_search_name_is_highlighted(metapix, second_company, query):
    def get_expected_data(schema: dict, query: str) -> dict:
        '''
        Convert `schema` into `schema_hightlighted`
        '''
        result = {}
        for group_title in schema.copy():
            if group_title == CURRENT_COMPANY:
                if query in schema[group_title]:
                    result[group_title] = query
                else:
                    result[group_title] = schema[group_title]
                continue

            result[group_title] = []
            for company_name in schema[group_title]:
                if query in company_name:  # TODO: deal with case sensitivity
                    result[group_title].append(query)

            if not result[group_title]:
                del result[group_title]
        return result

    choose_company_dialog = metapix.switch_company()
    schema = choose_company_dialog.schema
    choose_company_dialog.search(query)
    assert choose_company_dialog.schema_hightlighted == get_expected_data(schema, query)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Add Company: "E-Mail" and "Address" fields are compulsory')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1221')
def test_add_company_email_and_address_are_compulsory(metapix, driver):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    add_company_dialog = companies_page.open_add_new_company()
    add_company_dialog. \
        fill(
            name=generate_company_name(),
            type_=dialog_add_company.TYPE_EUC,
            email='',
            address='',
        )
    assert add_company_dialog.input_contact_email.tooltip == 'Field cannot be empty'
    assert add_company_dialog.input_contact_address.tooltip == 'Field cannot be empty'
    assert add_company_dialog.button_confirm.is_active() is False


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('If the state has not been changed, the save button should be disabled')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1213')
def test_save_button_is_disabled_if_state_not_changed(metapix):
    def check_input(control, save_button):
        old_value = control.value
        assert save_button.is_active() is False

        control.type_text('a')
        assert save_button.is_active() is True

        control.type_text(old_value, clear_with_keyboard=True)
        assert save_button.is_active() is False

    user_settings = metapix.open_user_settings()
    check_input(user_settings.input_first_name, user_settings.button_save_name)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check "password" field on login page')
def test_login_page_password_field_validation(metapix):
    login_page = metapix.logout()
    check_password_validation(login_page.password)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Company type is displayed in companies page')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1217')
def test_companies_settings_displays_company_type(metapix, driver):
    auth_ic_admin_in_browser(driver)
    companies_page = metapix.open_settings(). \
        open_companies()
    if companies_page.pages.total_amount < 10:
        raise PreconditionException
    companies_page.pages.set_value(consts.PAGINATION_MAX)
    types = {c['type'] for c in companies_page.schema}
    assert not (types - {
        UICompanyType.IC,
        UICompanyType.EUC,
        UICompanyType.SPC,
    })


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('The error message should be "Incorrect password" in case user is trying to change password while typing wrong old password')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/221')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/whole-project-tasks/-/issues/532')
def test_incorrect_password_tooltip(metapix, default_pwd):
    user_settings = metapix.open_user_settings()
    user_settings. \
        change_password(f'{default_pwd}_', f'{default_pwd}_', wait_spinner_disappeared=False)
    metapix.assert_tooltip('Error: Incorrect password')


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.tag('bug')
@allure.title('Check app does not crash if user clicks outside panel during panel is being hiding')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1433')
def test_app_crashes_if_click_during_hiding_panel(metapix):
    def double_click_outside_panel(panel):
        metapix._action_chains. \
            move_to_element_with_offset(panel.root, -panel.root.rect['width'], 0). \
            double_click(). \
            perform()

    with allure.step('Open any floating panel'):
        user_settings = metapix.open_user_settings()

    with allure.step('Double click outside the panel'):
        double_click_outside_panel(user_settings)

    with allure.step('Check app works (check random element is visible)'):
        assert is_element_exist(lambda: metapix.button_dashboard) is True


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check "password" field on settings page')
def test_user_settings_password_field_validation(metapix):
    user_settings = metapix.open_user_settings()
    check_password_validation(user_settings.input_new_password)
    check_password_validation(user_settings.input_old_password)


class GoToLoginDialog(Dialog):
    def __init__(self, *args, **kwargs):
        self._has_close_icon = False
        self.x_root = XPathType("//div[contains(@class, 'UIBasicDialog') and descendant::div[@class='UILogo']]")
        BasePage.__init__(self, *args, **kwargs)

    @property
    def title(self) -> str:
        return 'GoToLoginDialog'

    @property
    def message(self) -> str:
        element = self.get_desc_obj(XPathType("//div[@class='text-base']"))
        return element.text


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check message is shown if user does not have any company')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1383')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1489')
def test_message_if_no_company(metapix, client):
    login_page = metapix.logout()
    user_without_company = get_user_without_company(client)
    login_page.submit_data(
        user_without_company.email,
        user_without_company.current_password,
    )
    go_to_login_dialog = GoToLoginDialog(driver=metapix.driver)
    assert go_to_login_dialog.message == 'Currently, you don`t have any company within our cloud. '\
        'Please contact support@metapix.ai for further details. ' \
        'You may also delete your user account if needed.'


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('License Table. It is possible to activate valid license')
def test_enter_valid_license_key(metapix, not_activated_license):
    licenses_page = metapix.open_settings(). \
        open_licenses()
    expected_schema = sort_list_by_dict_key(
        licenses_page.schema + [
            {
                'key': not_activated_license.key,
                'days': not_activated_license.days,
                'cameras': not_activated_license.cameras,
            },
        ],
        key_to_sort='key',
    )
    licenses_page.activate_license(not_activated_license)
    assert sort_list_by_dict_key(licenses_page.schema, key_to_sort='key') == expected_schema


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check user avatar initials')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1426')
@pytest.mark.parametrize(
    'first_name,last_name,image_path,expected_initials',
    [
        ('   Test', '   User', None, 'TU'),
        (None, None, 'face/with-beard.jpg', ''),
        # TODO: 3th scenario: Если две верхних варианта не прошли проверки показываем стандартную заглушку в виде иконки
    ],
    ids=['initials', 'picture'],
)
@pytest.mark.usefixtures('teardown_restore_name')
@pytest.mark.usefixtures("teardown_delete_user_photo")
def test_user_avatar_initials(metapix, sender, first_name, last_name, image_path, expected_initials):
    # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1426#note_72514
    if first_name is not None:
        change_user_name(sender.client, first_name, last_name)
        metapix.refresh()
    user_settings = metapix.open_user_settings()
    if image_path:
        user_settings.open_upload_photo_dialog(sender.base_images_dir / image_path).confirm()  # TODO: do it with api
    assert user_settings.user_image.text == expected_initials


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('It is possible to add Administrator if you are logged in as Regular user')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1421')
@pytest.mark.parametrize('company_name_for_regular_user', ['TestRegularUserAsAdmin'])
def test_add_admin_as_regular_user(metapix, client, company_name_for_regular_user):
    # FYI: `company_name_for_regular_user` is company in which regular user is admin
    regular_user_client = get_second_user_client(client, role=ApiUserRole.regular)
    try:
        get_company_by_name(regular_user_client, company_name_for_regular_user)
    except CompanyDoesNotExistException:
        add_new_company(regular_user_client, company_name_for_regular_user)
    auth_user_in_browser(metapix.driver, regular_user_client)
    companies_page = metapix.open_settings(). \
        open_companies()

    with allure.step('Check roles are correct'):
        assert companies_page.get(regular_user_client.company.name).role == UIUserRole.REGULAR
        assert companies_page.get(company_name_for_regular_user).role == UIUserRole.ADMIN

    with allure.step('Check "role" dropdown have 2 options: admin and regular'):
        company_for_regular_user = companies_page.get(company_name_for_regular_user). \
            open_users()
        add_user_dialog = company_for_regular_user. \
            open_add_user_dialog()
        add_user_dialog.role.expand()
        assert add_user_dialog.role.options == {
            UIUserRole.ADMIN,
            UIUserRole.REGULAR,
        }


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check "registration" form fields')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1397')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1624')
def test_user_registration_fields(metapix, inbox, default_pwd):
    users_page = metapix.open_settings(). \
        open_users(metapix.driver.client)
    inbox = inbox.create_new()
    users_page.add_user(
        email=inbox.email,
        role=UIUserRole.REGULAR)
    registration_form = open_registration_form(inbox, metapix.driver, delete_mail=False)

    with allure.step('Check "email" field'):
        assert inbox.email == registration_form.email.value
        check_input_is_disabled(registration_form.email)

    with allure.step('Check password field'):
        check_show_password_ico(registration_form.password)
        check_password_validation(registration_form.password)

    with allure.step('Check first/last name fields'):
        check_name_validation(registration_form.first_name)
        check_name_validation(registration_form.last_name)

    with allure.step('Check there is no surplus controls in "Registration" form'):
        assert get_input_labels(registration_form) == ('E-Mail', 'First name', 'Last name', 'Password')
        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1397#note_72849
        assert get_button_labels(registration_form) == ('SUBMIT', )

    check_submit_button_active_if_all_fields_filled(
        registration_form.button_confirm,
        (
            (registration_form.first_name, get_random_name('First')),
            (registration_form.last_name, get_random_name('Last')),
            (registration_form.password, default_pwd),
        ),
    )


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check pagination widget layout (it stick to table)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1464')
@pytest.mark.usefixtures('teardown_delete_tokens')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_pagination_sticks_to_table(
        metapix: RootPage, client: ApiClient):
    def is_close(c1: int, c2: int) -> bool:
        return c1 - c2 < 3

    def check_pagination_sticks_to_table(table: BaseContentTable) -> None:
        with allure.step(f'Check position for {table}'):
            log.info(f'Check position for {table}')
            last_row = table._rows[-1]
            pages = table.pages.root
            assert is_close(last_row.location['x'] + last_row.size['width'], pages.location['x'] + pages.size['width'])
            assert is_close(last_row.location['y'] + last_row.size['height'], pages.location['y'])

    settings = metapix.open_settings()
    check_pagination_sticks_to_table(settings.open_users(client))
    check_pagination_sticks_to_table(settings.open_companies())
    check_pagination_sticks_to_table(settings.open_licenses())
    create_token(client, 'Token')
    check_pagination_sticks_to_table(settings.open_tokens())

    wl = create_watchlist(client, 'wl0', 'face')
    watchlists = metapix.open_watchlists()
    check_pagination_sticks_to_table(watchlists)

    add_predicates(client, wl, create_face_predicates(age=(10, 20)))
    check_pagination_sticks_to_table(watchlists.get('wl0').open_filters())


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('It should be possible to change datetime format in user settings')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1051')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1531')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1467')
@pytest.mark.parametrize(
    'default_fmt,new_fmt', [
        (DATETIME_FORMAT_DEFAULT, DATETIME_FORMAT_DMY_DASH_12H),
    ],
    ids=['dmy_dash_12h'],
)
@pytest.mark.usefixtures('teardown_restore_default_datetime_format')
@pytest.mark.usefixtures('teardown_delete_layouts')
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_change_datetime_format(
        metapix: RootPage,
        sender: ImageSender,
        default_fmt: DateTimeFormatType,
        new_fmt: DateTimeFormatType,
        another_driver: CustomWebDriver,
):
    # TODO: test 24h format
    # TODO: object thumbnail pop-up: not all cases are being tested
    with allure.step('Prepare data for test'):
        assert default_fmt != new_fmt  # self check
        create_token(sender.client, 'Token')
        sender.check_min_objects_count({'face': 1, 'vehicle': 1, 'person': 1})
        test = run_test(check_datetime_format(metapix, datetime_fmt=new_fmt))

    metapix.open_user_settings(). \
        change_time_settings(datetime_format=new_fmt). \
        close()

    with allure.step('Check object thumbnail from search'):
        search_results = metapix.search('face', fetch_more=False)
        thumbnail = search_results.thumbs.get_first()
        send_value_to_test(test, thumbnail)

    with allure.step('Check object thumbnail popup from search'):
        popup = thumbnail.open_popup()
        send_value_to_test(test, popup)
        popup.close()

    with allure.step('Check search panel date filters'):
        search_results.filters_panel.set_filters(date_from=Ago('-1d').dt)
        send_value_to_test(test, search_results.filters_panel)
        search_results.filters_panel.clear_filters()

    with allure.step('Check Object card main thumbnail'):
        card = thumbnail.open_card()
        send_value_to_test(test, card)

    with allure.step('Check Object card similar object thumbnail'):
        similar_object_thumb = card.similar_objects.get_first()
        send_value_to_test(test, similar_object_thumb)

    with allure.step('Check widgets'):
        metapix.open_dashboard()
        with allure.step('Check value widget update time'):
            value_widget = create_widget_api(metapix.dashboard, consts.WIDGET_VALUE, 'face')
            send_value_to_test(test, value_widget)

        with allure.step('Check live feed widget update time'):
            live_feed_widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, 'vehicle')
            send_value_to_test(test, live_feed_widget)

        with allure.step('Check live feed widget object thumbnail'):
            send_value_to_test(test, live_feed_widget.thumbs.get_first())

        with allure.step('Check bar chart widget tooltip'):
            bar_chart_widget = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, 'person')
            send_value_to_test(test, bar_chart_widget)

    with allure.step('Check widgets on shared layout'):
        auth_user_in_browser(another_driver)
        shared_layout = metapix.layout.share(another_driver)

        with allure.step('Check value widget update time'):
            send_value_to_test(test, shared_layout.get_widget(origin=value_widget))

        with allure.step('Check live feed widget update time'):
            live_feed_on_shared_layout = shared_layout.get_widget(origin=live_feed_widget)
            send_value_to_test(test, live_feed_on_shared_layout)

        with allure.step('Check live feed widget object thumbnail'):
            send_value_to_test(test, live_feed_on_shared_layout.thumbs.get_first())

        with allure.step('Check bar chart widget tooltip'):
            send_value_to_test(test, shared_layout.get_widget(origin=bar_chart_widget))

    with allure.step('Check shared widgets'):
        with allure.step('Check value widget update time'):
            send_value_to_test(test, value_widget.share(another_driver))

        with allure.step('Check live feed widget update time'):
            live_feed_shared_widget = live_feed_widget.share(another_driver)
            send_value_to_test(test, live_feed_shared_widget)

        with allure.step('Check live feed widget object thumbnail'):
            send_value_to_test(test, live_feed_shared_widget.thumbs.get_first())

        with allure.step('Check bar chart widget tooltip'):
            send_value_to_test(test, bar_chart_widget.share(another_driver))

    with allure.step('Check Settings -> Licenses table'):
        send_value_to_test(test, metapix.open_settings().open_licenses())

    with allure.step('Check Settings -> Tokens table'):
        send_value_to_test(test, metapix.open_settings().open_tokens())


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Licenses summary in case all licenses are expired')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1530')
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
def test_settings_licenses_summary_no_active_licenses(metapix: RootPage):
    def make_licenses_expired(request: Request, response: Response):
        if not request.path.endswith('auth-manager/v1/licenses/'):
            return
        body = get_body(response)
        if 'items' not in body:
            return
        for lic in body['items']:
            log.warning(f'amend {lic}')
            lic['is_expired'] = True
            lic['expired_at'] = lic['activated_at']
        body['cameras_count']['total_cameras'] = 0
        response.body = json.dumps(body).encode()
        response.headers.replace_header('Content-Length', len(response.body))  # seleniumwire.request.HTTPHeaders

    metapix.driver.response_interceptor = make_licenses_expired
    licenses_page = metapix.open_settings(). \
        open_licenses()
    assert licenses_page.licenses_summary == \
        'Licenses summary\n' \
        'No active licenses\n' \
        'You have used 4 channels recently'


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check user self deletion')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1499')
def test_delete_user_profile(
        metapix: RootPage, client: ApiClient, default_pwd: str):
    regular_user_client = get_second_user_client(client, role=ApiUserRole.regular)
    auth_user_in_browser(metapix.driver, regular_user_client)
    user_settings = metapix.open_user_settings()

    with allure.step('Check delete profile warning'):
        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1499#note_78745
        assert user_settings.delete_profile_warning == 'Once deleted, your entire data will be deleted and you will lose any access\n\n '\
            'You cannot delete your profile if you are the only remaining administrator in at least one company'

    with allure.step('Deleting profile causes opening login page'):
        user_settings.open_delete_profile_dialog().confirm()
        login_page = LoginPage(driver=metapix.driver)
        login_page.submit_data(regular_user_client.user.email, default_pwd, wait_disappeared=False)
        login_page.assert_tooltip("Error: Specified user doesn't exist")


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check "Created By" field in "Companies and Users"')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1411')
def test_SPC_created_by(
        metapix: RootPage, driver: CustomWebDriver, env_setup: Mapping[str, Any]):
    def get_company_by_type(table: CompaniesTable, type_: UICompanyType) -> Mapping[str, Any]:
        for company in table.companies:
            if company.type == type_.value:
                return company
        raise RuntimeError(f'No company with type: {type_.value}')
    auth_spc_admin_in_browser(driver)
    companies_table = metapix.open_settings(). \
        open_companies()
    assert 'Created By' in companies_table.table_headers
    companies_table.pages.set_value(consts.PAGINATION_MAX)
    ic_company = get_company_by_type(companies_table, UICompanyType.IC)
    assert ic_company.created_by == f'{env_setup["service_provider"]["company_name"]}, SPC'

    euc_company = get_company_by_type(companies_table, UICompanyType.EUC)
    assert euc_company.created_by == f'{config.user_config["integrator"]["company_name"]}, IC'


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check "Created By" field is not available for EUC admin')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1578')
def test_EUC_does_not_have_created_by_field(metapix: RootPage):
    companies_table = metapix.open_settings(). \
        open_companies()
    assert 'Created By' not in companies_table.table_headers


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Licenses page in case there are no licenses')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1549')
@pytest.mark.usefixtures('teardown_restore_driver_interceptors')
def test_settings_no_licenses(metapix: RootPage):
    def return_no_licenses(request: Request, response: Response):
        if not request.path.endswith('auth-manager/v1/licenses/'):
            return
        body = {
            'cameras_count': {'total_cameras': 0, 'total_in_use': 0},
            'items': [],
            'pagination': {'amount': 0, 'offset': 0, 'size': 0},
        }
        response.body = json.dumps(body).encode()
        response.headers.replace_header('Content-Length', len(response.body))  # seleniumwire.request.HTTPHeaders

    metapix.driver.response_interceptor = return_no_licenses
    licenses_page = metapix.open_settings(). \
        open_licenses()
    with allure.step('Check "No Licenses" dialog'):
        no_lic_dialog = IcoDialog(driver=metapix.driver, x_root=licenses_page.x_root)
        assert no_lic_dialog.buttons_labels == ['Activate new license', 'Activate demo license']
        assert no_lic_dialog.text == 'No Licenses\nCurrently, you haven’t activated any license. ' \
            'If you have a License Key, you can activate a New License\n' \
            'Otherwise, you can activate a Demo License and use our Solution for 30 days within the maximum capacity of 30 channels'


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Editing the Role: regular user cannot edit roles')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/710')
def test_edit_role_is_not_admin(metapix: RootPage, client: ApiClient):
    with allure.step('Login as Regular user'):
        regular_user_client = get_second_user_client(client, role='regular')
        auth_user_in_browser(metapix.driver, regular_user_client)

    with allure.step('Check there is no "Modify role" button for any user'):
        users_page = metapix.open_settings(). \
            open_users(regular_user_client)
        for user_row in users_page.users:
            with allure.step(f'Check {user_row} does not have "Modify role" button'):
                assert not is_element_exist(lambda: user_row._button_modify_role)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Editing the Role: admin is able to edit roles')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/710')
def test_edit_role_admin(metapix: RootPage, client: ApiClient):
    def check_modify_role(users_page: UsersPage, email: EmailType, new_role: UIUserRole, check_refresh: bool):
        user_row = users_page.get_user(email)
        expected_role_str = new_role.lower().capitalize()
        with allure.step(f'Modify role Regular -> Admin for {email}'):
            with allure.step('Invoke and check "Modify Role" dialog'):
                edit_role_dialog = user_row.open_modify_role_dialog()
                assert edit_role_dialog.message == f'Do you want to change {user_row.name}`s role to {expected_role_str}?'
            
            with allure.step('Confirm modifying role'):
                edit_role_dialog.confirm()
                metapix.assert_tooltip('The User\'s role has been updated')
            
                with allure.step(f'Check entry {user_row} changed'):
                    assert user_row.role == expected_role_str

            if check_refresh:
                with allure.step('Check table entry state after refresh'):
                    users_page.refresh()
                    user_row = users_page.get_user(email)
                    assert user_row.role == expected_role_str

    with allure.step('Prepare data'):
        with allure.step('Request another Regular user'):
            second_user = get_second_user(client, role='regular')
        users_page = metapix.open_settings(). \
            open_users(client)
    check_modify_role(users_page, second_user.email, UIUserRole.ADMIN, True)
    check_modify_role(users_page, second_user.email, UIUserRole.REGULAR, False)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Editing the Role: Self')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/710')
@pytest.mark.skip('https://metapix-workspace.slack.com/archives/C03KBMWC146/p1728302991278889')
def test_edit_role_self():
    '''
    FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1728302896758319
         https://metapix-workspace.slack.com/archives/C03KBMWC146/p1728302991278889
    '''
    raise NotImplementedError


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Editing the Role: the user (whose role had been changed) in another session')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/710')
def test_edit_role_user_in_another_session(metapix: RootPage, client: ApiClient, another_driver: CustomWebDriver):
    def can_edit_another_user(users_table: UsersPage, email: EmailType) -> bool:
        user = users_table.get_user(email)
        return is_element_exist(lambda: user._button_modify_role)

    with allure.step('Prepare data'):
        with allure.step('Request another Regular user'):
            second_user_client = get_second_user_client(client, role='regular')
        users_page = metapix.open_settings(). \
            open_users(client)
        second_user_users_page = auth_user_in_browser(another_driver, second_user_client). \
            open_settings(). \
            open_users(second_user_client)
        assert not can_edit_another_user(second_user_users_page, client.user.email)

    with allure.step('Modify role (Regular -> Admin) for another user'):
        users_page.get_user(second_user_client.user.email). \
            open_modify_role_dialog(). \
            confirm()

    with allure.step('Check role changes have applied for another user'):
        second_user_users_page.refresh()
        assert can_edit_another_user(second_user_users_page, client.user.email)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check the current retention period')
def test_check_current_retention_period(metapix: RootPage):
    retentiond_period = metapix.open_settings().open_retention_period()
    assert retentiond_period.period_value == 90
