import logging
import time
import re
from typing import Mapping
from typing import Literal

import allure
from selenium.common.exceptions import TimeoutException

from tools.webdriver import WebElement
from tools.types import XPathType

from pages.button import Button
from pages.base_page import BasePage

log = logging.getLogger(__name__)


class PaginationException(Exception):
    pass


class PageButton(Button):
    def __init__(
            self,
            label: str,
            x_root: XPathType = XPathType(""),
            *args, **kwargs):
        self._label = label
        self.x_root = x_root + f"//button[@title='{label}']"
        BasePage.__init__(self, *args, **kwargs)

    def is_active(self) -> bool:
        try:
            self.get_object(self.x_root + "//span[@class='MuiTouchRipple-root']")
            return True
        except TimeoutException:
            return False


class Pagination(BasePage):
    def __init__(self, x_root: XPathType, *args, **kwargs):
        self.x_root = x_root + XPathType("//p[text()='Rows per page:']/..")
        super().__init__(*args, **kwargs)

    @property
    def button_prev(self) -> PageButton:
        return PageButton(label="Previous page", x_root=self.x_root, driver=self._driver)

    @property
    def button_next(self) -> PageButton:
        return PageButton(label="Next page", x_root=self.x_root, driver=self._driver)

    @property
    def button_rows_per_page(self) -> WebElement:
        return self.get_object(self.x_root + "//div[contains(@class, 'MuiSelect-root')]")

    @property
    def value(self) -> str:
        return self.button_rows_per_page.text

    @property
    def schema(self) -> Mapping[Literal['first'] | Literal['last'] | Literal['total'], int]:
        '''
        Parse string: 1-10 of 17
        '''
        pattern = re.compile(r'(\d+)-(\d+) of (\d+)')
        text = self.get_objects(self.x_root + '//p')[1].text
        match_result = pattern.match(text)
        if not match_result:
            raise RuntimeError
        return {
            'first': int(match_result.group(1)),
            'last': int(match_result.group(2)),
            'total': int(match_result.group(3)),
        }

    @property
    def first_ix(self) -> int:
        return self.schema['first']

    @property
    def last_ix(self) -> int:
        return self.schema['last']

    @property
    def total_amount(self) -> int:
        return self.schema['total']

    def get_next(self) -> None:
        with allure.step(f"{self}: users: next page"):
            log.info(f"{self}: users: next page")
            if self.button_next.is_active() is not True:
                raise PaginationException
            self.button_next.click()
            time.sleep(2)
            assert self.button_prev.is_active() is True

    def get_prev(self) -> None:
        with allure.step(f"{self}: users: prev page"):
            log.info(f"{self}: users: prev page")
            if self.button_prev.is_active() is not True:
                raise PaginationException
            self.button_prev.click()
            time.sleep(2)
            assert self.button_next.is_active() is True

    def set_value(self, value: int) -> None:
        with allure.step(f"{self}: change 'rows per page' value: {self.value} -> {value}"):
            log.info(f"{self}: change 'rows per page' value: {self.value} -> {value}")
            self.button_rows_per_page.click()
            time.sleep(1)
            self.get_object(XPathType(f'//li[text()="{value}"]')).click()
            self.waiter(timeout=1).until(lambda x: self.value == str(value))
            time.sleep(2)
