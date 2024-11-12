import time
from typing import Iterable
import logging

import allure
from selenium.common.exceptions import StaleElementReferenceException

import consts
from tools.retry import retry
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.base_page import NoElementException
from pages.base_page import PageDidNotLoaded
from pages.widgets import BarChartNotShared
from pages.widgets import BarChartShared
from pages.widgets import LineChartNotShared
from pages.widgets import LineChartShared
from pages.widgets import LiveFeedNotShared
from pages.widgets import LiveFeedShared
from pages.widgets import NotSharedWidget
from pages.widgets import PieChartNotShared
from pages.widgets import PieChartShared
from pages.widgets import ValueNotShared
from pages.widgets import ValueShared
from pages.widgets.dialog_choose_type import ChooseWidgetType

log = logging.getLogger(__name__)


class NoAddWidgetButtonException(Exception):
    pass


class NoWidgetException(Exception):
    pass


widget_class_not_shared = {
    consts.WIDGET_VALUE: ValueNotShared,
    consts.WIDGET_LIVE_FEED: LiveFeedNotShared,
    consts.WIDGET_PIE_CHART: PieChartNotShared,
    consts.WIDGET_LINE_CHART: LineChartNotShared,
    consts.WIDGET_BAR_CHART: BarChartNotShared,
}

widget_class_shared = {
    consts.WIDGET_VALUE: ValueShared,
    consts.WIDGET_LIVE_FEED: LiveFeedShared,
    consts.WIDGET_PIE_CHART: PieChartShared,
    consts.WIDGET_LINE_CHART: LineChartShared,
    consts.WIDGET_BAR_CHART: BarChartShared,
}


class DashboardPage(BasePage):
    path = '/'
    x_root = XPathType("//div[contains(@class, 'grid-layout')]")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, check_primary_element_timeout=8, **kwargs)
        self.wait_spinner_disappeared()

    @property
    @retry(StaleElementReferenceException)
    def button_add_widget(self) -> WebElement:
        try:
            return self.get_object(
                XPathType('//p[text()="Add widget"]'),
                is_clickable=True,
            )
        except NoElementException as exc:
            raise NoAddWidgetButtonException from exc

    @property
    def widgets_titles(self) -> Iterable[str]:
        try:
            titles_elements = self.get_objects(
                XPathType(self.x_root + "//div[child::h6]"),
                wait_presence=True,
            )
        except NoElementException:
            return []
        titles_elements = sorted(titles_elements, key=lambda t: t.location['y'])
        titles: Iterable[str] = [t.text for t in titles_elements]
        log.info(f'Widget titles on dashboard: {titles}')
        return titles

    @retry(PageDidNotLoaded)
    @retry(StaleElementReferenceException)
    def _click_button_add_widget(self) -> ChooseWidgetType:
        """
        This code was separated to be able to **retry** it.
        """
        self.button_add_widget.click()
        time.sleep(1)
        return ChooseWidgetType(driver=self._driver)

    def open_widget_builder(self) -> ChooseWidgetType:
        # TODO: this method opens "Choose Widget Type" dialog actually
        # So we should rename it to "choose_widget_type"
        with allure.step('Open widget builder'):
            log.info('Open widget builder')
            self.scroll_to_element(self.button_add_widget)
            return self._click_button_add_widget()

    def get_widget(self, title=None, widget_type=None, origin=None) -> NotSharedWidget:
        with allure.step(f'Look for widget {widget_type=} title="{title}"'):
            log.info(f'Look for widget {widget_type=} {origin=}title="{title}"')
            if origin:
                title = origin.title
                widget_type = origin.type
            if title not in self.widgets_titles:
                raise NoWidgetException(f'"{title}" does not exist. available: {self.widgets_titles}')

            return widget_class_not_shared[widget_type](title=title, driver=self._driver)
