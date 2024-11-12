import logging

import consts
from tools import wait_objects_arrive
from pages.base_page import NoElementException
from pages.widgets.base_chart import BaseChartWidget

log = logging.getLogger(__name__)


class ValueWidgetAutorefreshException(Exception):
    """ ValueWidget doesn't have autorefresh button """


class ValueWidget(BaseChartWidget):
    type = consts.WIDGET_VALUE

    @property
    def value(self):
        wait_objects_arrive()
        try:
            value_text = self.text.replace(',', '')
            if value_text.endswith("m"):
                value = float(value_text[:-1])
                return int(value * 1e6)
            elif value_text.endswith("k"):
                value = float(value_text[:-1])
                return int(value * 1e3)
            else:
                return int(value_text)
        except NoElementException:
            return None

    @property
    def objects_count(self):
        """ Common interface for all widgets to get amount of objects """
        wait_objects_arrive()
        return self.value

    def set_detalization(self, *args, **kwargs):
        raise RuntimeError('Value Widget does not have timeslice detalization')
