import logging

import allure

from tools import parse_object_type
from pages.button import Button
from pages.widgets import ValueNotShared
from pages.widgets import LiveFeedNotShared
from pages.widgets import LineChartNotShared
from pages.widgets import BarChartNotShared
from pages.widgets import PieChartNotShared
from pages.widgets.base_settings import BaseWidgetSettings

log = logging.getLogger(__name__)


class WidgetsBuilder(BaseWidgetSettings):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title="Create widget", **kwargs)

    @property
    def button_ok(self):
        """ Button 'Add widget'"""
        return Button(driver=self._driver, label="Add widget", x_root=self.x_root)

    @property
    def button_select_type(self):
        """ Return bak to 'Choose widget type' dialog"""
        # TODO: test this button
        return Button(driver=self._driver, label="Select type", x_root=self.x_root)

    def _widget_postprocessing(self, widget):
        self.wait_disappeared()
        widget.wait_spinner_disappeared()
        return widget

    def create_value_widget(self, object_type, title=None, filters=None):
        base = parse_object_type(object_type)[0]
        with allure.step(f"Create value widget: {base}"):
            log.info(f"Create value widget: {base}")
            title = title or f'{base.capitalize()} Value Widget'
            self.set_title(title)
            self.select_base(base)
            if filters:
                self.set_filters(**filters)
            self.apply()
            return self._widget_postprocessing(
                ValueNotShared(title=title, driver=self._driver),
            )

    def create_pie_chart_widget(self, object_type, title=None, filters=None):
        base = parse_object_type(object_type)[0]
        with allure.step(f"Create pie chart: {base}"):
            log.info(f"Create pie chart: {base}")
            title = title or f'{base.capitalize()} Pie Chart Widget'
            self.set_title(title)
            self.select_base(base)
            if filters:
                self.set_filters(**filters)
            self.apply()
            return self._widget_postprocessing(
                PieChartNotShared(title=title, driver=self._driver),
            )

    def create_line_chart_widget(self, object_type, title=None, filters=None):
        base = parse_object_type(object_type)[0]
        # if report-timeslices has not been finished by the moment - script will fail
        with allure.step(f"Create line chart: {base}"):
            log.info(f"Create line chart: {base}")
            title = title or f'{base.capitalize()} Line Chart Widget'
            self.button_line_chart.click()
            self.set_title(title)
            self.select_base(base)
            if filters:
                self.set_filters(**filters)
            self.apply()
            return self._widget_postprocessing(
                LineChartNotShared(title=title, driver=self._driver),
            )

    def create_bar_chart_widget(self, object_type, title=None, filters=None):
        base = parse_object_type(object_type)[0]
        with allure.step(f"Create bar chart: {base}"):
            log.info(f"Create bar chart: {base}")
            title = title or f'{base.capitalize()} Bar Chart Widget'
            # if report-timeslices has not been finished by the moment - script will fail
            self.button_bar_chart.click()
            self.set_title(title)
            self.select_base(base)
            if filters:
                self.set_filters(**filters)
            self.apply()
            return self._widget_postprocessing(
                BarChartNotShared(title=title, driver=self._driver),
            )

    def create_live_feed_widget(self, object_type, title=None, filters=None):
        base = parse_object_type(object_type)[0]
        with allure.step(f"Create live feed widget: {base}"):
            log.info(f"Create live feed widget: {base}")
            title = title or f'{base.capitalize()} Live Feed Widget'
            self.set_title(title)
            self.select_base(base)
            if filters:
                self.set_filters(**filters)
            self.apply(clickhouse_lag=False)
            return self._widget_postprocessing(
                LiveFeedNotShared(title=title, driver=self._driver),
            )
