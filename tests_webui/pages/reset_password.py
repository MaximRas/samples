from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import allure

from tools.types import EmailType

from pages.dialog import Dialog
from pages.input_field import Input_v0_48_4
from pages.input_field import InputPassword_v0_48_4
from pages.button import Button

if TYPE_CHECKING:
    from pages.login import LoginPage

log = logging.getLogger(__name__)


class ChangePasswordDialog(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Information',
            is_mui=False,
            *args, **kwargs,
        )
        if 'We have sent a confirmation code to your email address' not in self.message:
            raise RuntimeError(f'Wrong message in dialog: "{self.message}"')

    @property
    def input_email(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            x_root=self.x_root,
            label='E-Mail',
            driver=self.driver,
        )

    @property
    def input_confirmatin_code(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            x_root=self.x_root,
            label='Confirmation code',
            driver=self.driver,
        )

    @property
    def input_password(self) -> InputPassword_v0_48_4:
        return InputPassword_v0_48_4(x_root=self.x_root, label='Password', driver=self.driver)

    @property
    def button_change_password(self) -> Button:
        return Button(x_root=self.x_root, label='Change password', is_mui=False, driver=self.driver)

    def change_password(self, confirmation_code: str, password: str) -> LoginPage:
        from pages.login import LoginPage

        with allure.step(f'Change password {confirmation_code=} {password=}'):
            log.info(f'Change password {confirmation_code=} {password=}')
            assert self.input_email.value == self.driver.client.user.email  # self check
            self.input_confirmatin_code.type_text(confirmation_code)
            self.input_password.type_text(password)
            self.button_change_password.click()
            self.assert_tooltip('Password changed successfully')
            self.driver.client.user.current_password = password
            return LoginPage(driver=self.driver)


class SendCodeDialog(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Information',
            is_mui=False,
            *args, **kwargs,
        )
        if 'If you need to reset your password, please enter your email address' not in self.message:
            raise RuntimeError(f'Wrong message in dialog: "{self.message}"')

    @property
    def button_send_code(self) -> Button:
        return Button(x_root=self.x_root, label='Send a code', is_mui=False, driver=self.driver)

    @property
    def input_email(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            x_root=self.x_root,
            label='E-Mail',
            driver=self._driver,
        )

    def send_code(self, email: EmailType) -> ChangePasswordDialog:
        with allure.step(f'Send a code for {email}'):
            log.info(f'Send a code for {email}')
            self.input_email.type_text(email)
            self.button_send_code.click()
            self.assert_tooltip('A confirmation code has been sent to your email')
            return ChangePasswordDialog(driver=self.driver)
