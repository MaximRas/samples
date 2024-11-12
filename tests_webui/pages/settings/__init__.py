import logging
import time

import allure

from pages.settings.retention_period import RetentionPeriodPage
from tools import config
from tools import join_url
from tools.client import ApiClient
from tools.types import XPathType
from tools.users import get_active_company

from pages.navigation import BaseNavigationPage
from pages.settings.companies import CompaniesTable
from pages.settings.licenses import LicensesPage
from pages.settings.tokens import GatewayTokensPage
from pages.settings.users import UsersPage
from pages.user_settings import UserSettingsPanel

log = logging.getLogger(__name__)


class SettingsNavigationPage(BaseNavigationPage):
    path = '/settings/general'

    def __init__(self, *args, **kwargs):
        super().__init__(title='Settings', *args, **kwargs)

    def open_licenses(self) -> LicensesPage:
        with allure.step('Open settings -> licenses'):
            log.info('Open settings -> licenses')
            self._find_navigation_entry('Licenses').click()
            return LicensesPage(driver=self._driver)

    def open_tokens(self) -> GatewayTokensPage:
        with allure.step('Open settings -> tokens'):
            log.info('Open settings -> tokens')
            self._find_navigation_entry('Gateway Tokens').click()
            return GatewayTokensPage(driver=self._driver)

    def open_companies(self) -> CompaniesTable:
        with allure.step('Open settings -> companies'):
            log.info('Open settings -> companies')
            self._find_navigation_entry('Companies and Users').click()
            return CompaniesTable(driver=self._driver)

    def open_users(self, client: ApiClient) -> UsersPage:
        """ Open users of active company """
        with allure.step('Open users for current companies (with direct link)'):
            # TODO: and carry out refactoring of appropriate tests
            company = get_active_company(client)
            company_url = join_url(config.web_url, f'/settings/companies/{company.id}')
            log.info(f'Open users for current companies (with direct url: {company_url})')
            self.open(company_url)
            self.wait_spinner_disappeared()
            return UsersPage(driver=self._driver, company_name=company.name)

    def open_user_settings(self) -> UserSettingsPanel:
        with allure.step('Open settings -> User settings'):
            log.info('Open settings -> User settings')
            button = self.get_desc_obj(XPathType('//div[@class="UIMainMenuButtonContent" and descendant::span="User Settings"]'))
            button.click()
            time.sleep(2)  # skip animation
            return UserSettingsPanel(driver=self._driver)

    def open_retention_period(self) -> RetentionPeriodPage:
        with allure.step('Open Settings -> Retention period page'):
            log.info('Open Settings -> Retention period page')
            self._find_navigation_entry('Retention Period').click()
            return RetentionPeriodPage(driver=self._driver)
