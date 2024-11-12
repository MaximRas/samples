import logging

import allure

from pages.base_page import BasePage
from pages.button import Button
from pages.login import LoginPage
from tools.types import UrlType
from tools.types import XPathType
from tools.webdriver import get_main_js_workaround

log = logging.getLogger(__name__)


class LegacyLoginPage(BasePage):
    path = '/log-in/'
    x_root = XPathType("//div[@role='dialog' and descendant::input[@name='login']]")

    @property
    def _primary_url(self) -> UrlType:
        url = super()._primary_url.replace('/beta', '')
        return UrlType(url)

    @property
    def _button_switch_to_beta_version(self) -> Button:
        return Button(x_root=self.x_root, driver=self.driver, label='Switch to new version')

    def switch_to_beta_version(self):
        with allure.step('Switch to beta version'):
            log.info('Switch to beta version')
            self._button_switch_to_beta_version.click()
            self.wait_disappeared()
            get_main_js_workaround(driver=self.driver, url=None, refresh=True)
            return LoginPage(driver=self.driver)
