import logging
import time

import allure

import consts
from pages.dialog import Dialog
from pages.button import Button
from pages.widgets.builder import WidgetsBuilder

log = logging.getLogger(__name__)


class ChooseWidgetType(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title="Choose widget type", **kwargs)

    @property
    def button_cancel(self):
        """ Button to close builder """
        return Button(driver=self._driver, label="Cancel", x_root=self.x_root)

    @property
    def button_bar_line_chart(self):
        return self.get_object(self.x_root + '//p[text()="Bar / Line Chart"]')

    @property
    def button_pie_chart(self):
        return self.get_object(self.x_root + '//p[text()="Pie Chart"]')

    @property
    def button_live_feed(self):
        return self.get_object(self.x_root + '//p[text()="Live Feed"]')

    @property
    def button_value(self):
        return self.get_object(self.x_root + '//p[text()="Numeric Value"]')

    @property
    def _builder(self):
        return WidgetsBuilder(driver=self._driver)

    def create_value_widget(self, *args, **kwargs):
        builder = self.choose_widget_type(consts.WIDGET_VALUE)
        return builder.create_value_widget(*args, **kwargs)

    def create_live_feed_widget(self, *args, **kwargs):
        builder = self.choose_widget_type(consts.WIDGET_LIVE_FEED)
        return builder.create_live_feed_widget(*args, **kwargs)

    def create_pie_chart_widget(self, *args, **kwargs):
        builder = self.choose_widget_type(consts.WIDGET_PIE_CHART)
        return builder.create_pie_chart_widget(*args, **kwargs)

    def create_line_chart_widget(self, *args, **kwargs):
        builder = self.choose_widget_type(consts.WIDGET_BAR_LINE_CHART)
        return builder.create_line_chart_widget(*args, **kwargs)

    def create_bar_chart_widget(self, *args, **kwargs):
        builder = self.choose_widget_type(consts.WIDGET_BAR_LINE_CHART)
        return builder.create_bar_chart_widget(*args, **kwargs)

    def choose_widget_type(self, widget_type, delay=3):
        WIDGET_TYPE_TO_LOCATOR = {
            consts.WIDGET_BAR_LINE_CHART: self.button_bar_line_chart,
            consts.WIDGET_PIE_CHART: self.button_pie_chart,
            consts.WIDGET_LIVE_FEED: self.button_live_feed,
            consts.WIDGET_VALUE: self.button_value,
        }
        WIDGET_TYPE_TO_LOCATOR[widget_type].click()
        self.wait_disappeared()
        time.sleep(delay)
        return self._builder

    def create_widget(self, widget_type, *args, **kwargs):
        create_method = {
            consts.WIDGET_VALUE: self.create_value_widget,
            consts.WIDGET_LIVE_FEED: self.create_live_feed_widget,
            consts.WIDGET_PIE_CHART: self.create_pie_chart_widget,
            consts.WIDGET_LINE_CHART: self.create_line_chart_widget,
            consts.WIDGET_BAR_CHART: self.create_bar_chart_widget,
        }
        return create_method[widget_type](*args, **kwargs)

    def cancel(self):
        with allure.step(f'{self}: cancel'):
            log.info(f'{self}: cancel')
            self.button_cancel.click()
            self.wait_disappeared()
