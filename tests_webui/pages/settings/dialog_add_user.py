import logging

import allure

from tools.types import EmailType
from tools.types import XPathType
from pages.confirm_dialog import ConfirmDialog
from pages.input_field import Input_v0_48_4
from pages.dropdown import Select_v0_48_4

log = logging.getLogger(__name__)


class AddNewUserPage(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            title='Add New User',
            confirm_label="Add",
            check_primary_element_timeout=8,
            is_mui=False,
            is_mui_cancel_button=False,
            is_mui_confirm_button=False,
            **kwargs,
        )

    @property
    def caption(self) -> str:
        element = self.get_desc_obj(XPathType("//div[contains(@class, 'UISectionMessage')]"))
        return element.text

    @property
    def role(self) -> Select_v0_48_4:
        return Select_v0_48_4(label='Role', driver=self._driver, has_clear_button=True)

    @property
    def email(self) -> Input_v0_48_4:
        return Input_v0_48_4(driver=self._driver, label="E-Mail", x_root=self.x_root)

    def skip(self) -> None:
        '''
        For semantic sake: we don't cancel creating a new user, we just skip
        creating a new user after a new company has been created
        '''
        with allure.step('Skip creating a new user'):
            log.info('Skip creating a new user')
            self.cancel()

    def add_user(self, email: EmailType, role: str) -> None:
        with allure.step(f'{self}: add user {email=} {role=}'):
            log.info(f'{self}: add user {email=} {role=}')
            self.email.type_text(email)
            self.role.select_option(role)
            self.confirm(delay=0, wait_disappeared=False)
            tooltip = f'{role[0] + role[1:].lower()} added successfully'  # "Regular User" -> "Regular user"
            self.assert_tooltip(tooltip, timeout=15)
            self.wait_spinner_disappeared()
