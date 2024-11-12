from abc import abstractmethod
import logging
import time
from typing import Iterable
from typing import Sequence
from typing import Mapping

import allure

from tools import UndefinedElementException
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import find_elements
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.button import NoButtonException
from pages.pagination import Pagination

log = logging.getLogger(__name__)

ICO_PENCIL = IcoType('M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34a.9959.9959 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z')
ICO_TRASH_CAN = IcoType('M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z')


def get_button(
        row: WebElement,
        ico: IcoType,
        postfix_xpath: str = '',
) -> WebElement:
    buttons = find_elements(row, XPathType(f'.//button[descendant::*[@d="{ico}"]]' + postfix_xpath))
    if len(buttons) > 1:
        raise UndefinedElementException
    if not buttons:
        raise NoButtonException
    return buttons[0]


def get_column(
        row: WebElement,
        ix: int,
        xpath: XPathType = XPathType("./td"),
) -> WebElement:
    return find_elements(row, xpath)[ix]


class BaseContentTable(BasePage):
    expected_headers: Sequence[str] = tuple()

    def __init__(self, title: str, *args, **kwargs):
        self.x_root = XPathType(
            "//div[contains(@class, 'UIWidgetContainer') and "
            "not(contains(@class, 'UINavigation')) and descendant::"
            f"div[@class='UIWidgetTitle' and text()=\"{title}\"]]"
        )

        super().__init__(
            check_primary_element_timeout=kwargs.pop('check_primary_element_timeout', 10),
            *args, **kwargs,
        )
        time.sleep(2)

    @property
    @abstractmethod
    def schema(self) -> Sequence[Mapping]:
        raise NotImplementedError

    @property
    def _rows(self) -> Iterable[WebElement]:
        return self.get_objects(XPathType(self.x_root + "//tbody//tr"))

    @property
    def pages(self) -> Pagination:
        return Pagination(driver=self._driver, x_root=self.x_root)

    @property
    def table_name(self) -> str:
        header = self.get_desc_obj(XPathType("//div[@class='UIWidgetTitle']"), min_opacity=0.75)
        return header.get_attribute("textContent")

    @property
    def table_headers(self) -> Sequence[str]:
        headers = [header.text.strip() for header in self.get_objects(XPathType(self.x_root + '//th'))]
        return tuple(filter(lambda x: x, headers))


class NavigationEntry:
    def __init__(self, element, parent):
        self._element = element
        self._parent = parent

    def __str__(self):
        return f"NavigationEntry '{self.title}'"

    @property
    def link(self):
        return self._element

    @property
    def title(self):
        return self.link.text

    def click(self):
        with allure.step(f"{self}: open {self.title}"):
            log.info(f"{self}: open {self.title}")
            self.link.click()
            self._parent.wait_spinner_disappeared()


class BaseNavigationPage(BasePage):
    def __init__(self, driver, title, *args, **kwargs):
        self._x_navigation = XPathType(
            "//div[contains(@class, 'UIWidgetContainer') "
            "and contains(@class, 'UINavigation') and descendant::"
            f"div[@class='UIWidgetTitle' and text()='{title}']]"
        )

        self.x_root = f"{self._x_navigation}/.."
        self._driver = driver
        self._x_content = XPathType(f"{self.x_root}/div[2]")
        super().__init__(*args, check_primary_element_timeout=8, driver=self._driver, **kwargs)
        self.wait_spinner_disappeared()

    @property
    def navigation(self):
        entries = []
        for navigation_entry in self.get_objects(XPathType(f"{self.x_root}/div[1]//a")):
            entries.append(NavigationEntry(navigation_entry, self))
        return entries

    def _find_navigation_entry(self, title):
        for entry in self.navigation:
            if entry.title == title:
                return entry
        raise RuntimeError(f'Navigation entry hasn\'t been found: {title}')
