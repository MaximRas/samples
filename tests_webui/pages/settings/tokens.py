"""
Page Object for table "Gateway Tokens"
TODO: support pagination
"""

import logging

import allure

from tools.getlist import GetList
from tools.types import StrDateType

from pages.base_page import is_element_exist
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.copy_value_dialog import CopyValueDialog
from pages.set_value_dialog import SetValueDialog
from pages.navigation import BaseContentTable
from pages.navigation import get_column

log = logging.getLogger(__name__)


class AddTokenDialog(SetValueDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            input_label="Token name",
            title="Generate New Token",
            confirm_label="Generate",
            is_mui_confirm_button=False,
            is_mui=False,
            *args, **kwargs,
        )


class Token:
    def __init__(self, element, parent):
        self._element = element
        self._parent = parent

    def __str__(self):
        return f"Token {self.name}"

    @property
    def name(self):
        return get_column(self._element, 0).text

    @property
    def generated_at(self) -> StrDateType:
        return StrDateType(get_column(self._element, 1).text)

    @property
    def button_delete(self):
        return get_column(self._element, 0, xpath=".//button")

    def open_delete_dialog(self):
        self.button_delete.click()
        return ConfirmDialog(
            title='Do you really want to delete this token?',
            driver=self._parent._driver,
            confirm_label='Delete',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            has_section_message=False,
        )

    def delete(self):
        with allure.step(f"{self}: delete"):
            log.info(f"{self}: delete")
            self.open_delete_dialog().confirm(delay=0.5)
            self._parent.assert_tooltip('The token has been deleted')
            self._parent.wait_spinner_disappeared()
            assert is_element_exist(lambda: self._element) is False


class GatewayTokensPage(BaseContentTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title='Gateway tokens', **kwargs)

    @property
    def button_add_new_token(self):
        return Button('Add token', driver=self.driver, is_mui=False, x_root=self.x_root)

    @property
    def tokens(self):
        return GetList([Token(row, self) for row in self._rows])

    @property
    def schema(self):
        schema_ = []
        for token in self.tokens:
            schema_.append(
                {
                    "name": token.name,
                    "generated at": token.generated_at,
                }
            )
        return schema_

    @property
    def copy_token_dialog(self):
        return CopyValueDialog(
            driver=self._driver,
            title="Please copy token value to the Metapix Plugin",
            has_close_icon=True,
        )

    def open_add_token_dialog(self):
        with allure.step('Open "Add token" dialog'):
            log.info('Open "Add token" dialog')
            self.button_add_new_token.click()
            return AddTokenDialog(driver=self._driver)

    def add_token(self, token_name):
        with allure.step(f"{self}: add token: {token_name}"):
            log.info(f"{self}: add token: {token_name}")
            self.open_add_token_dialog(). \
                set_value(token_name). \
                confirm(delay=0, wait_disappeared=False)
            self.assert_tooltip('Token has been added')
            self.wait_spinner_disappeared()
            token_value = self.copy_token_dialog.value
            if not token_value:
                raise RuntimeError('Token has not been copied')
            self.copy_token_dialog.cancel()
        return token_value
