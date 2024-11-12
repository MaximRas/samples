import logging
import time

import allure

from tools.types import XPathType
from pages.root import RootPage
from pages.base_page import BasePage
from pages.base_page import PageDidNotLoaded
from pages.switch_company import SwitchSystemDialog

log = logging.getLogger(__name__)


class DWLoginPage(BasePage):
    x_root = XPathType("//div[contains(@class, 'authorize-main')]")

    @property
    def button_email(self):
        return self.get_object(self.x_root + "//input[@id='authorizeEmail']")

    @property
    def button_password(self):
        return self.get_object(self.x_root + "//input[@id='authorizePassword']")

    @property
    def button_process(self):
        return self.get_object(self.x_root + "//div[@class='process-button']")

    def login(self, email, password):
        with allure.step(f"{self}: login with: {email} / {password}"):
            log.info(f"{self}: login with: {email} / {password}")
            self.button_email.send_keys(email)
            self.button_process.click()
            time.sleep(2)
            self.button_password.send_keys(password)
            self.button_process.click()
            self.wait_disappeared()

            with allure.step('Look for "Switch system" dialog'):
                log.info('Look for "Switch system" dialog')
                try:
                    select_system_dialog = SwitchSystemDialog(
                        driver=self._driver,
                    )
                    select_system_dialog.select_by_index(0)
                except PageDidNotLoaded:
                    log.warning('"Switch system" dialog not found')

            return RootPage(driver=self._driver).wait_spinner_disappeared()
