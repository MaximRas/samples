import time
import logging
from functools import cached_property

import allure
from selenium.webdriver.remote.shadowroot import ShadowRoot
from selenium.webdriver.common.by import By

from tools.webdriver import find_element
from tools.webdriver import CustomWebDriver
from tools.webdriver import WebElement

log = logging.getLogger(__name__)


class FeedbackDialog:
    '''
    https://developer.mozilla.org/en-US/docs/Web/API/ShadowRoot
    https://stackoverflow.com/questions/55761810/how-to-automate-shadow-dom-elements-using-selenium
    '''
    def __init__(self, driver: CustomWebDriver):
        self.driver = driver

    @cached_property
    def _shadow_host(self) -> WebElement:
        return find_element(self.driver, "//div[@id='sentry-feedback']")

    @cached_property
    def _shadow_root(self) -> ShadowRoot:
        return self.driver.execute_script('return arguments[0].shadowRoot', self._shadow_host)

    @property
    def _input_message(self) -> WebElement:
        return self._shadow_root.find_element(By.CSS_SELECTOR, 'textarea#message')

    @property
    def _button_send(self) -> WebElement:
        return self._shadow_root.find_element(By.CSS_SELECTOR, 'button[aria-label="Send"]')

    @property
    def _button_cancel(self) -> WebElement:
        return self._shadow_root.find_element(By.CSS_SELECTOR, 'button[aria-label="Cancel"]')

    def send_feedback(self, message: str) -> None:
        with allure.step(f'Send feedback: "{message}"'):
            log.info(f'Send feedback: "{message}"')
            self._input_message.send_keys(message)
            self._button_send.click()
            time.sleep(3)
