from abc import abstractmethod
import logging

import allure

from tools import NoDataFoundException
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage

log = logging.getLogger(__name__)


class WidgetException(Exception):
    pass


class AutoRefreshStateException(WidgetException):
    pass


class BaseWidget(BasePage):
    @property
    @abstractmethod
    def objects_count(self) -> int:
        raise NotImplementedError

    @property
    def text_element(self) -> WebElement:
        return self.get_object_no_wait(
            XPathType(
                self.x_root + "//*[name()='svg' and contains(@class, 'UITextWidget')]/*[name()='text']"))

    @property
    def text(self):
        return self.text_element.text

    def assert_objects_count(self, expected_count: int):
        if expected_count == 0:
            raise NoDataFoundException
        with allure.step(f'Check objects count. Expected: {expected_count}'):
            objects_count = self.objects_count
            log.info(f'{self}: check objects count. Actual: {objects_count}, expected: {expected_count}')
            assert objects_count == expected_count, \
                f'{self}: wrong objects count. actual: {objects_count}, expected: {expected_count}'
