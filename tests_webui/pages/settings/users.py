from typing import Any
from typing import Iterable
from typing import Sequence

import logging
import allure
from typing_extensions import Self
from typing_extensions import override

from tools import check_enum_has_value
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.ico_button import get_div_tooltip_ico_button
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.types import IcoType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.base_page import is_element_exist
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.navigation import BaseContentTable
from pages.navigation import get_column
from pages.settings.dialog_add_user import AddNewUserPage
from pages.settings.companies import UIUserRole

log = logging.getLogger(__name__)


class NoDeleteButtonException(Exception):
    pass


class UsersTableRow:
    def __init__(self, element: WebElement, parent: BasePage):
        self._element = element
        self._parent = parent

    def __str__(self):
        return f"user {self.name}"

    @property
    def name(self) -> str:
        text = get_column(self._element, 0).text
        user_name = text.split('\n')[-1]
        return user_name

    @property
    def role(self) -> str:
        text = get_column(self._element, 1).text
        return check_enum_has_value(UIUserRole, text)

    @property
    def email(self) -> EmailType:
        text = get_column(self._element, 2).text
        return EmailType(text)

    @property
    def _button_modify_role(self) -> IcoButton:
        ico = IcoType('M215.384-160q-23.057 0-39.221-16.163Q160-192.327 160-215.384v-529.232q0-23.057 16.163-39.221Q192.327-800 215.384-800h357.308l-30.769 30.769H215.384q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v529.232q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h529.232q9.23 0 16.923-7.692 7.692-7.693 7.692-16.923v-331.847L800-578v362.616q0 23.057-16.163 39.221Q767.673-160 744.616-160H215.384ZM480-480Zm-80 80v-104.616l365.077-365.077q4.384-4.384 10-6.077 5.615-1.692 12-1.692 5.615 0 11.257 1.808 5.642 1.808 10.205 6.192l56.846 55.539q5.532 5.111 7.92 11.477 2.388 6.365 2.388 12.79 0 6.425-1.975 12.25t-6.795 10.791L500.769-400H400Zm444.923-388.846L787.846-849l57.077 60.154ZM430.769-430.769h57.308l276.077-276.077-28.385-28.923-31.462-29.692-273.538 273.307v61.385Zm305-305-31.462-29.692 31.462 29.692 28.385 28.923-28.385-28.923Z')
        return get_div_tooltip_ico_button(self._element, ico)

    @property
    def _button_delete(self) -> IcoButton:
        ico = IcoType('M295.615-160q-22.442 0-38.913-16.471-16.471-16.471-16.471-38.913v-518.462H200v-30.77h154.154v-26.154h251.692v26.154H760v30.77h-40.231v518.462q0 23.057-16.163 39.221Q687.443-160 664.385-160h-368.77ZM689-733.846H271v518.462q0 10.769 7.308 17.692 7.307 6.923 17.307 6.923h368.77q9.231 0 16.923-7.692Q689-206.154 689-215.384v-518.462ZM395.461-273.692h30.77v-378.231h-30.77v378.231Zm138.308 0h30.77v-378.231h-30.77v378.231ZM271-733.846v543.077-543.077Z')
        return get_div_tooltip_ico_button(self._element, ico, no_button_exception=NoDeleteButtonException)

    def open_modify_role_dialog(self) -> ConfirmDialog:
        with allure.step(f'Open modify role dialog for {self}'):
            log.info(f'Open modify role dialog for {self}')
            self._button_modify_role.click()
            return ConfirmDialog(
                title='Modify User',
                driver=self._parent.driver,
                confirm_label='Modify',
                has_section_message=False,
                is_mui=False,
                is_mui_confirm_button=False,
                is_mui_cancel_button=False,
            )

    def open_delete_dialog(self) -> ConfirmDialog:
        with allure.step(f'Open delete dialog for {self}'):
            log.info(f'Open delete dialog for {self}')
            self._button_delete.click()
            return ConfirmDialog(
                title='Delete User',
                driver=self._parent.driver,
                confirm_label='YES',
                has_section_message=False,
                is_mui=False,
                is_mui_confirm_button=False,
                is_mui_cancel_button=False,
            )

    def delete(self):
        with allure.step(f"{self}: delete"):
            log.info(f"{self}: delete")
            user_name = self.name  # save name bofore deleting this user
            if user_name == 'Invited User':
                # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1439#note_72843
                user_name = self.email
            delete_dialog = self.open_delete_dialog()
            assert delete_dialog.message == f"Do you really want to delete '{user_name}' ?"
            delete_dialog.confirm(wait_disappeared=False)
            self._parent.assert_tooltip(f"'{user_name}' deleted successfully")
            delete_dialog.wait_disappeared()
            self._parent.wait_spinner_disappeared()
            assert is_element_exist(lambda: self._element) is False


class UsersPage(BaseContentTable):
    def __init__(
            self,
            company_name: CompanyNameType,
            *args, **kwargs):
        self._company_name = company_name
        super().__init__(*args, title=f"Users List in '{self._company_name}'", **kwargs)

    @override
    def refresh(self, *args, **kwargs) -> Self:
        return super().refresh(company_name=self._company_name)

    @property
    def button_add_new_user(self) -> Button:
        return Button(x_root=self.x_root, label='Add user', driver=self._driver, is_mui=False)

    @property
    def users(self) -> Iterable[UsersTableRow]:
        return [UsersTableRow(row, self) for row in self._rows]

    @property
    def schema(self) -> Sequence[dict[str, Any]]:
        schema_ = []
        for user in self.users:
            schema_.append(
                {
                    "name": user.name,
                    "email": user.email,
                    "role": user.role,
                }
            )
        return schema_

    def add_user(self, *args, **kwargs) -> EmailType:
        self.open_add_user_dialog().add_user(*args, **kwargs)
        return kwargs["email"]

    def open_add_user_dialog(self) -> AddNewUserPage:
        with allure.step(f"{self}: open 'Add new user' dialog"):
            log.info(f"{self}: open 'Add new user' dialog")
            self.button_add_new_user.click()
            return AddNewUserPage(driver=self._driver)

    def get_user(self, email: EmailType) -> UsersTableRow:
        with allure.step(f"{self}: looking for user: {email}"):
            log.info(f"{self}: looking for user: {email}")
            for user in self.users:
                # FYI: (why email is in lower case?) client/metapix-frontend-app/-/issues/705
                if user.email == email:
                    return user
            raise RuntimeError(f"No user with email: {email}")
