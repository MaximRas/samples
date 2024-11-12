import logging
import time

import allure

from tools.mailinator import Inbox
from tools.types import XPathType
from pages.base_page import BasePage
from pages.dialog import Dialog
from pages.button import Button
from pages.input_field import InputFieldLegacy
from pages.license_server.root import LicenseServerRootPage

log = logging.getLogger(__name__)


class LoginPage(BasePage):
    x_root = XPathType(f"//div[{Dialog.X_MUI_DIALOG_CONTAINER_PREDICATE} and descendant::label='E-Mail']")
    path = '/log-in'

    @property
    def email(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label="E-Mail",
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def confirmation_code(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label='Confirmation code',
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def password(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label='Password',
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def button_sign_in(self):
        return Button(label="Sign In", driver=self._driver, x_root=self.x_root)

    @property
    def button_change_password(self):
        return Button(label="Change password", driver=self._driver, x_root=self.x_root)

    @property
    def button_send_code(self):
        return Button(label="Send a code", driver=self._driver, x_root=self.x_root)

    @property
    def link_reset_password(self):
        return self.get_object(self.x_root + "//a[text()='Reset Password']")

    def reset_password(self, email, password):
        with allure.step(f"{self}: reset password: {email}/ {password}"):
            log.info(f"{self}: reset password for {email} / {password}")

            self.link_reset_password.click()
            assert self.parsed_url.path == "/reset-password"
            self.email.type_text(email)
            self.button_send_code.click()
            self.assert_tooltip('A confirmation code has been sent to your email')

            time.sleep(5)  # wait untill previous tooltip disappeared
            inbox = Inbox(email=email)
            code = inbox.get_confirmation_code()
            self.confirmation_code.type_text(code)
            self.password.type_text(password)
            self.button_change_password.click()
            self.assert_tooltip('Password changed successfully')
            return self.__class__(driver=self._driver)

    def login(self, email, password, return_page=LicenseServerRootPage):
        with allure.step(f"{self}: login as {email} / {password}"):
            log.info(f"{self}: login as {email} / {password}")
            self.email.type_text(email)
            self.password.type_text(password)
            self.button_sign_in.click()
            self.wait_disappeared()
            self.wait_spinner_disappeared()
            return return_page(driver=self._driver)
