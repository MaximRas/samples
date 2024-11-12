import logging
import time

import allure
from selenium.common.exceptions import TimeoutException

from tools.types import XPathType
from pages.base_page import BasePage
from pages.widgets.base_widget import AutoRefreshStateException

log = logging.getLogger(__name__)


class OpenSharedWidgetException(Exception):
    pass


class BaseSharedWidget(BasePage):
    x_root = XPathType("//div[@id='root']/div[contains(@class, 'MuiBox-root')]")

    def __init__(self, *args, **kwargs):
        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1129
        self._driver = kwargs.get('driver')  # get `driver` in advance to be able to use `wait_spinner_disappeared`
        self.wait_spinner_disappeared()
        super().__init__(*args, **kwargs)

    @property
    def state(self):
        from pages.widgets import get_base_state
        return get_base_state(self, is_shared=True)

    @property
    def button_autorefresh(self):
        return self.get_object("//span[descendant::input and contains(@class, 'MuiCheckbox-root')]", is_clickable=True)

    def _is_autorefresh_enabled(self):
        return "-checked" in self.button_autorefresh.get_attribute("class")

    def enable_autorefresh(self, delay=2):
        with allure.step(f"{self}: enable autorefresh"):
            log.info(f"{self}: enable autorefresh")
            if self._is_autorefresh_enabled():
                raise RuntimeError("Autorefresh is already enabled")
            self.button_autorefresh.click()
            self.assert_autorefresh_enabled()
            time.sleep(delay)

    def disable_autorefresh(self):
        with allure.step(f"{self}: disable autorefresh"):
            log.info(f"{self}: disable autorefresh")
            if not self._is_autorefresh_enabled():
                raise RuntimeError("Autorefresh is already disabled")
            self.button_autorefresh.click()
            self.assert_autorefresh_disabled()
            time.sleep(2)

    def assert_autorefresh_enabled(self):
        with allure.step(f"{self}: check autorefresh enabled"):
            log.info(f"{self}: check autorefresh enabled")
            try:
                self.waiter(timeout=3).until(lambda x: self._is_autorefresh_enabled() is True)
            except TimeoutException:
                raise AutoRefreshStateException(self)

    def assert_autorefresh_disabled(self):
        with allure.step(f"{self}: check autorefresh disabled"):
            log.info(f"{self}: check autorefresh disabled")
            try:
                self.waiter(timeout=3).until(lambda x: self._is_autorefresh_enabled() is False)
            except TimeoutException:
                raise AutoRefreshStateException(self)
