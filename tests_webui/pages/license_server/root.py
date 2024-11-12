import logging

import allure

from tools.types import XPathType
from pages.base_page import BasePage
from pages.button import Button
from pages.license_server.integrators import IntegratorsPage
from pages.license_server.licenses import LicensesPage

log = logging.getLogger(__name__)


class LicenseServerRootPage(BasePage):
    x_root = XPathType("//div[@id='root' and descendant::span='Log Out']")

    @property
    def licenses(self):
        return LicensesPage(driver=self._driver)

    @property
    def button_logout(self):
        return Button(label="Log Out", x_root=self.x_root, driver=self._driver)

    @property
    def button_integrators(self):
        return self.get_object("//a[@class='MuiMenuLink' and @title='Integrators']")

    def logout(self):
        from .login import LoginPage

        with allure.step(f"{self}: logout"):
            log.info(f"{self}: logout")
            self.button_logout.click()
            self.wait_disappeared()
            return LoginPage(driver=self._driver)

    @allure.step('Open integrators list')
    def open_integrators_list(self):
        self.button_integrators.click()
        return IntegratorsPage(driver=self._driver)
