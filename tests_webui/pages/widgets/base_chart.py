from abc import abstractmethod
from datetime import datetime
from typing import Any
from typing import Optional
from typing import NoReturn
from typing import Iterable
from typing import Sequence
import logging
import time

import allure
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from typing_extensions import Self

import consts
from consts import ICO_BUTTON_BAR_CHART
from consts import ICO_BUTTON_LINE_CHART
from tools.getlist import GetList
from tools import wait_objects_arrive
from tools.color import Color
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import CustomWebDriver
from tools.webdriver import WebElement
from tools.webdriver import find_element
from tools.webdriver import find_elements

from pages.button import Button
from pages.datetime_utils import DatetimeDialog
from pages.dialog import Dialog
from pages.widgets.base_widget import BaseWidget
from pages.widgets.header import WidgetHeaderIconButton

log = logging.getLogger(__name__)

ADJUST_MENU_COLUMN_LABEL = 'Column Label'
ADJUST_MENU_LEGEND = 'Legend'
ADJUST_MENU_TIME_INTERVAL = 'Time Interval'


class LegendButtonStateException(Exception):
    pass


class TimesliceAlreadyHasValue(Exception):
    pass


class ChangeTimesliceException(Exception):
    pass


class ChangeDetalizationException(Exception):
    pass


X_TIMESLICE_CONTAINER = XPathType("//div[@role='group' and contains(@class, 'MuiToggleButtonGroup-root')]")


class CustomTimeslice(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title='Select custom date range', **kwargs)

    @property
    def range_from(self) -> DatetimeDialog:
        return DatetimeDialog(driver=self._driver, x_root=XPathType(self.x_root + "//div[@class='mui-picker'][1]"))

    @property
    def range_to(self) -> DatetimeDialog:
        return DatetimeDialog(driver=self._driver, x_root=XPathType(self.x_root + "//div[@class='mui-picker'][2]"))

    @property
    def button_submit(self) -> Button:
        return Button(x_root=self.x_root, label="Submit", driver=self._driver)

    def set_dates(
            self,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None) -> Self:
        if date_from:
            log.info(f'{self}: set date from: {date_from}')
            self.range_from.set_datetime(date_from)
        if date_to:
            log.info(f'{self}: set date to: {date_to}')
            self.range_to.set_datetime(date_to)
        if date_from and date_to:
            # TODO: set date_from again
            log.info(f'{self}: set date from: {date_from}')
            self.range_from.set_datetime(date_from)
        return self

    def submit(self):
        with allure.step(f"{self}: submit"):
            log.info(f"{self}: submit")
            self.button_submit.click()
            self.wait_disappeared()
            self.assert_no_error_tooltips()


class LegendButton:
    def __init__(self, element: WebElement, driver: CustomWebDriver):
        self._element = element
        self._driver = driver

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.parent_title + self._element.text

    @property
    def parent_title(self) -> str:
        try:
            parent_element = find_element(self._element, XPathType("../span"))
            return parent_element.text
        except NoSuchElementException:
            return ""

    @property
    def _circle(self) -> WebElement:
        return find_element(self._element, XPathType(".//span"))

    @property
    def color(self) -> Color:
        return Color(self._circle.value_of_css_property("background-color"))

    def is_enabled(self) -> bool:
        child_span = find_element(self._element, XPathType("./span"))
        bg_color = child_span.value_of_css_property("background-color")
        if bg_color == consts.COLOR_DISABLED_BUTTON:
            return False
        return True

    def switch(self):
        with allure.step(f"{self} switch state"):
            log.info(f"{self} switch state")
            prev_state = self.is_enabled()
            self._element.click()  # TODO: too fast???
            waiter = WebDriverWait(self._driver, timeout=2, poll_frequency=0.2)
            try:
                waiter.until(lambda x: self.is_enabled() != prev_state)
            except TimeoutException as exc:
                raise LegendButtonStateException("Color didn't changed") from exc
            log.info(f"{self} state changed {prev_state} -> {self.is_enabled()}")


class BaseChartWidget(BaseWidget):
    # TODO: check available bases for widget. E.g. pie chart doesn't support 'person'
    def _get_timeslice_button_by_value(self, value: str):
        return self.get_object(
            XPathType(
                self.x_root +
                X_TIMESLICE_CONTAINER +
                "//button[contains(@class, 'MuiToggleButton') and child::span='{value}']".format(value=value)
            )
        )

    @abstractmethod
    def _change_adjust_menu(self, label: str, desired_state: bool) -> NoReturn:
        raise NotImplementedError

    @property
    def selected_timeslice_value(self) -> str:
        element_selected = self.get_desc_obj(
            XPathType(
                X_TIMESLICE_CONTAINER + "//button[contains(@class, 'selected')]"))
        return element_selected.get_attribute("value")

    @property
    def legend(self) -> Sequence[LegendButton]:
        legend = []
        for legend_element in self.get_objects(XPathType(self.x_root + "//div[child::span[@style and not(@data-z-index)]]")):
            legend.append(LegendButton(element=legend_element, driver=self._driver))
        return GetList(legend)

    @property
    def legend_schema(self) -> Iterable[dict]:
        schema_ = []
        for button in self.legend:
            schema_.append(
                {
                    'name': button.name,
                    'color': str(button.color),
                    'is_enabled': button.is_enabled(),
                    'location': button._element.location,
                }
            )
        return schema_

    @property
    def timeslice_container(self) -> WebElement:
        return self.get_desc_obj(X_TIMESLICE_CONTAINER)

    @property
    def timeslice_schema(self) -> dict[str, Any]:
        schema_ = {'buttons': [], 'active_button': None}
        for button in self.get_objects(XPathType(self.x_root + X_TIMESLICE_CONTAINER + "//button")):
            schema_['buttons'].append(button.text)
        assert len(schema_['buttons']) > 0
        schema_['active_button'] = self.selected_timeslice_value
        schema_['location'] = self.root.location
        schema_['size'] = self.root.size
        return schema_

    @property
    def button_detalization(self) -> WebElement:
        # TODO: create Listbox class (also suitable for layout listbox)
        return self.get_object(
            XPathType(self.x_root + X_TIMESLICE_CONTAINER + '//div[@aria-haspopup="listbox"]'),
            is_clickable=True,
        )

    @property
    def detalization_value(self) -> str:
        text = self.button_detalization.get_attribute("textContent")
        return text.lower()

    def enable_legend(self):
        self._change_adjust_menu(ADJUST_MENU_LEGEND, True)

    def disable_legend(self):
        self._change_adjust_menu(ADJUST_MENU_LEGEND, False)

    def enable_time_intervals(self):
        self._change_adjust_menu(ADJUST_MENU_TIME_INTERVAL, True)

    def disable_time_intervals(self):
        self._change_adjust_menu(ADJUST_MENU_TIME_INTERVAL, False)

    def open_custom_timeslice(self):
        with allure.step(f'Open "custom timeslice" dialog for "{self}"'):
            log.info(f'{self}: open "custom timeslice" dialog')
            button = self._get_timeslice_button_by_value("Custom")
            button.click()
            # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1130
            # will be reproduced if "Custom timeslice" is submitted too fast. Delay fixes it
            time.sleep(2)
            return CustomTimeslice(driver=self._driver)

    def set_custom_timeslice(self, date_from=None, date_to=None):
        def _get_widget_state(widget):
            from pages.widgets.live_feed import LiveFeedWidget

            if LiveFeedWidget in widget.__class__.__mro__:
                return widget.grid_state
            return widget.chart_state

        prior_state = _get_widget_state(self)
        custom_timeslice = self.open_custom_timeslice()
        custom_timeslice.set_dates(date_from=date_from, date_to=date_to)
        custom_timeslice.submit()
        self.waiter(timeout=5, poll_frequency=1).until(
            lambda x: _get_widget_state(self) != prior_state)

    def set_timeslice(self, timeslice, delay=5):
        with allure.step(f"{self}: set timeslice: {timeslice}"):
            if timeslice == self.selected_timeslice_value:
                raise TimesliceAlreadyHasValue(self.selected_timeslice_value)
            log.info(f"{self}: set timeslice: {timeslice}")
            button = self._get_timeslice_button_by_value(timeslice)
            button.click()
            self.assert_no_error_tooltips()
            self.waiter(timeout=2).until(lambda x: self.selected_timeslice_value == timeslice)
            wait_objects_arrive()
            time.sleep(delay)
        return self

    def set_detalization(self, detalization, delay=5):
        with allure.step(f"{self}: set detalization: {detalization}"):
            log.info(f"{self}: set detalization: {detalization}")
            if self.detalization_value == detalization:
                raise RuntimeError(f'{self}: already has detalization {detalization}')
            self.button_detalization.click()
            time.sleep(1)  # TODO: remove wait
            detalization_button = self.get_object(f'//li[text()="{detalization.upper()}"]')
            detalization_button.click()  # NB: don't use relative xpath. detalization field list isn't inside widget
            self.assert_no_error_tooltips()
            self.wait(
                lambda x: self.detalization_value == detalization,
                ChangeDetalizationException(f'Required: {detalization}, actual: {self.detalization_value}'),
                timeout=1,   # small timeout since execution of `assert_no_error_tooltips` takes some time
            )
            time.sleep(delay)  # TODO: remove wait. required to prevent error: StaleElementReferenceException: Message: stale element reference: element is not attached to the page document


class BaseBarLineChartWidget(BaseChartWidget):
    X_TIMESCALES = '//*[name()="g" and contains(@class, "highcharts-xaxis-labels")]/*'
    X_Y_SCALE = "//*[name()='g' and contains(@class, 'highcharts-yaxis-labels')]//*[name()='text']"

    @abstractmethod
    def _init_header_ico_button(self, ico: IcoType):
        raise NotImplementedError

    @property
    def button_bar_chart(self) -> WidgetHeaderIconButton:
        return self._init_header_ico_button(ICO_BUTTON_BAR_CHART)

    @property
    def button_line_chart(self) -> WidgetHeaderIconButton:
        return self._init_header_ico_button(ICO_BUTTON_LINE_CHART)

    @property
    def labels_x(self) -> Iterable[WebElement]:
        return self.get_objects(XPathType(self.x_root + BaseBarLineChartWidget.X_TIMESCALES))

    @property
    def labels_y(self) -> Iterable[WebElement]:
        return self.get_objects(XPathType(self.x_root + BaseBarLineChartWidget.X_Y_SCALE))

    @property
    def labels_x_text(self) -> Iterable[str]:
        labels = []
        for elabel in self.labels_x:
            if find_elements(elabel, XPathType("./*")):
                labels.append("\n".join(
                    [lbl.text for lbl in find_elements(elabel, XPathType("./*"))]))
            else:
                labels.append(elabel.text)
        return labels

    @property
    def timeslice_schema(self) -> dict[str, Any]:
        schema = super().timeslice_schema
        schema['detalization_value'] = self.detalization_value
        return schema

    def switch_to_line_chart(self):
        from pages.widgets import LineChartNotShared
        from pages.widgets import SwitchBarLineChartExeption

        with allure.step(f"{self}: switch type bar -> line"):
            log.info(f"{self} switch type: bar -> line")

            if not self.button_bar_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Bar chart" button is not active')
            if self.button_line_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Line chart" button is active')

            self.button_line_chart.switch_on()
            new_widget = LineChartNotShared(title=self.title, driver=self._driver)

            if self.button_bar_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Bar chart" button is active')
            if not self.button_line_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Line chart" button is not active')

        return new_widget

    def switch_to_bar_chart(self):
        from pages.widgets import BarChartNotShared
        from pages.widgets import SwitchBarLineChartExeption

        with allure.step(f"{self}: switch type line -> bar"):
            log.info(f"{self} switch type: line -> bar")

            if self.button_bar_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Bar chart" button is active')
            if not self.button_line_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Line chart" button is not active')

            self.button_bar_chart.switch_on()
            new_widget = BarChartNotShared(title=self.title, driver=self._driver)

            if not self.button_bar_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Bar chart" button is not active')
            if self.button_line_chart.is_highlighted():
                raise SwitchBarLineChartExeption('"Line chart" button is active')

        return new_widget
