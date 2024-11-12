import logging
import time
from typing import Iterable

import allure
from selenium.common.exceptions import ElementClickInterceptedException
from strenum import StrEnum

from tools import check_enum_has_value
from tools.retry import retry
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.types import IcoType
from tools.types import XPathType
from tools.ico_button import get_ico_button
from tools.webdriver import WebElement

from pages.button import Button
from pages.navigation import BaseContentTable
from pages import BaseTableRow
from pages.settings.dialog_add_company import AddNewCompanyDialog

log = logging.getLogger(__name__)


class UIUserRole(StrEnum):
    ADMIN = 'Administrator'
    REGULAR = 'Regular User'


class UICompanyType(StrEnum):
    EUC = 'EUC'
    IC = 'IC'
    SPC = 'SPC'


class Company(BaseTableRow):
    def __str__(self) -> str:
        return f"Company {self.name}"

    @property
    def name(self) -> CompanyNameType:
        return CompanyNameType(self.get_field_by_header('Company Name'))

    @property
    def contact_email(self) -> EmailType:
        text = self.get_field_by_header('Contact E-mail')
        return EmailType(text)

    @property
    def contact_address(self) -> str:
        return self.get_field_by_header('Address')

    @property
    def type(self) -> UICompanyType:
        text = self.get_field_by_header('Company Type')
        return check_enum_has_value(UICompanyType, text)

    @property
    def created_by(self) -> str:
        return self.get_field_by_header('Created By')

    @property
    def role(self) -> UIUserRole:
        role_ = self.get_field_by_header('Role')
        # FYI: transform "Regular user" -> "Regular User"
        if not role_:
            return None
        role_ = ' '.join([w.capitalize() for w in role_.split()])
        return check_enum_has_value(UIUserRole, role_)

    @property
    def button_users(self) -> WebElement:
        ICO_USERS = IcoType('M102.61-215.38v-57.85q0-28.08 14.54-48.12 14.54-20.03 41.12-31.79 56.88-25.01 105.77-39.01 48.88-14 118.96-14 70.08 0 118.46 14 48.39 14 106.04 39.01 25.81 11.76 40.46 31.79 14.66 20.04 14.66 48.12v57.85H102.61Zm630.77 0v-55.54q0-43.77-17.72-74.64-17.73-30.87-45.97-51.29 37.46 7.23 72.31 18.12 34.85 10.88 61.34 23.98 23.74 12.83 38.89 34.8 15.16 21.97 15.16 49.03v55.54H733.38ZM383-504.85q-49.88 0-82.83-32.94-32.94-32.94-32.94-82.83 0-49.88 32.94-82.44 32.95-32.56 82.83-32.56 49.88 0 82.44 32.56Q498-670.5 498-620.62q0 49.89-32.56 82.83T383-504.85Zm271.92-115.77q0 49.89-32.55 82.83-32.56 32.94-82.72 32.94-2.65 0-4.61-.34-1.96-.35-4.5-1.27 18.86-21.74 28.55-50.74 9.68-28.99 9.68-63.13 0-34.13-10.58-61.71-10.57-27.58-27.65-52.73 1.77.08 4.5-.38 2.73-.47 4.5-.47 50.27 0 82.83 32.56 32.55 32.56 32.55 82.44ZM133.38-246.15h498.47v-27.08q0-16-8.73-29.08-8.74-13.07-28.89-23.69-53.54-26.62-100.23-38-46.69-11.38-111-11.38T271.88-364q-46.8 11.38-100.34 38-20.16 10.62-29.16 23.69-9 13.08-9 29.08v27.08Zm249.24-289.47q35.92 0 60.26-24.34 24.35-24.35 24.35-60.27t-24.35-60.27q-24.34-24.35-60.26-24.35-35.93 0-60.27 24.35Q298-656.15 298-620.23t24.35 60.27q24.34 24.34 60.27 24.34Zm0 289.47Zm0-374.08Z')
        return get_ico_button(
            self._element,
            ico=ICO_USERS,
            button_tag=XPathType('.//a'),
        )

    @retry(ElementClickInterceptedException)
    def open_users(self):
        from .users import UsersPage

        with allure.step(f'Open users: {self}'):
            log.info(f'Open users: {self}')
            company_name = self.name
            self.button_users.click()
            self._parent.wait_spinner_disappeared()
            return UsersPage(driver=self._parent._driver, company_name=company_name)


class CompaniesTable(BaseContentTable):
    expected_headers = (
        'Company Name',
        'Contact E-mail',
        'Address',
        'Company Type',
        'Created By',
        'Role',
        'Actions',
        'Users',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, title='List of Companies', **kwargs)
        extra_headers = set(self.table_headers) - set(self.expected_headers)
        if extra_headers:
            raise RuntimeError(f'Unexpected headers: {extra_headers}')

    @property
    def companies(self) -> Iterable[Company]:
        return [Company(row, self) for row in self._rows]

    @property
    def button_add_new_company(self) -> Button:
        return Button(label="Add company", driver=self._driver, is_mui=False)

    @property
    def schema(self) -> list[dict]:
        # TODO: use `self.table_headers` ???
        schema_ = []
        for company in self.companies:
            schema_.append(
                {
                    "name": company.name,
                    "role": company.role,
                    "type": company.type,
                    "email": company.contact_email,
                    "address": company.contact_address,
                }
            )
        return schema_

    def get(self, name) -> Company:
        for company in self.companies:
            if company.name == name:
                return company
        raise RuntimeError(f"There is no company with name:{name}")

    def open_add_new_company(self, delay=1) -> AddNewCompanyDialog:
        with allure.step(f"{self}: open 'Add new company' dialog"):
            log.info(f"{self}: open 'Add new company' dialog")
            time.sleep(delay)  # wait DOM get stable
            self.button_add_new_company.click()
            return AddNewCompanyDialog(driver=self._driver)
