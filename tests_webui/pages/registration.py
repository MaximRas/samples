import logging
from typing import Sequence
from urllib.parse import urlparse

import allure
from selenium.webdriver.support.wait import WebDriverWait

from tools import config
from tools.mailinator import Inbox
from tools.webdriver import CustomWebDriver

from pages.ico_dialog import IcoDialog
from pages.base_page import BasePage
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.input_field import Input_v0_48_4
from pages.input_field import InputPassword_v0_48_4

log = logging.getLogger(__name__)


class SuccessDialog(BasePage):
    def __init__(self, *args, **kwargs):
        self.x_root = "//div[@class='UIWidgetPlaceholder']"
        super().__init__(*args, **kwargs)

    @property
    def button_login(self) -> Button:
        return Button(
            x_root=self.x_root,
            label='Log in',
            is_mui=True,
            driver=self.driver,
        )

    @property
    def text(self) -> Sequence[str]:
        return self.root.text.split('\n')


class RegistrationDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        # This dialog uses UIDialog class instead of UIBasicDialog
        super().__init__(
            title='Registration',
            is_mui=False,
            is_mui_confirm_button=False,
            custom_x_root="//div[contains(@class, 'UIDialog') and descendant::div='Registration']",
            check_primary_element_timeout=10,
            *args, **kwargs,
        )

    @property
    def first_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(driver=self._driver, label='First name')

    @property
    def email(self) -> Input_v0_48_4:
        # TODO: Check field is disabled
        return Input_v0_48_4(driver=self._driver, label='E-Mail', x_root=self.x_root)

    @property
    def last_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(driver=self._driver, label='Last name')

    @property
    def password(self) -> InputPassword_v0_48_4:
        return InputPassword_v0_48_4(driver=self._driver, label='Password')

    def submit(
            self,
            first_name: str = 'New',
            last_name: str = 'User',
            password: str = config.user_config['_default_pwd'],
    ):
        with allure.step(f'Submit registration form: {first_name=} {last_name=} {password=}'):
            self.first_name.type_text(first_name)
            self.last_name.type_text(last_name)
            self.password.type_text(password)
            self.confirm()
            return IcoDialog(driver=self.driver)


def open_registration_form(inbox: Inbox, driver: CustomWebDriver, delete_mail: bool) -> RegistrationDialog:
    with allure.step('Look for registration link'):
        inbox.wait_any_message(
            WebDriverWait(driver, timeout=9, poll_frequency=3)
        )
        registration_url = inbox.get_registration_link(timeout=1)
        parsed_url = urlparse(registration_url)
        if config.is_beta and not parsed_url.path.startswith('/beta'):
            log.error(f'Fix url that does not start with /beta: {registration_url}')
            registration_url = registration_url.replace(parsed_url.path, f'/beta{parsed_url.path}')

    with allure.step('Open registration form'):
        driver.get(registration_url)
        return RegistrationDialog(driver=driver)


def complete_registration(inbox: Inbox, driver: CustomWebDriver, *args, **kwargs):
    with allure.step(f'Complete registration for {inbox}'):
        registration_page = open_registration_form(inbox, driver, delete_mail=True)

        with allure.step(f'Fill registration form with {args} {kwargs}'):
            success_dialog = registration_page.submit(*args, **kwargs)

        with allure.step('Check "success" message'):
            assert success_dialog.text == 'Success\nUser registered succesfilly'
