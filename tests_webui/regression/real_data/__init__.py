from contextlib import suppress
from datetime import datetime

import allure

from pages.widgets import NotSharedChart
from pages.widgets.base_chart import TimesliceAlreadyHasValue


def switch_2w_timeslice(widget: NotSharedChart):
    '''
    Sometimes there there is a gap in data.
    So let's use 2w timeslice to be sure there is some data
    '''
    with suppress(TimesliceAlreadyHasValue):
        widget.set_timeslice('2w')


def set_custom_timeslice(widget: NotSharedChart):
    with allure.step('Set custom timeslice to have objects of all types'):
        widget.open_custom_timeslice(). \
            set_dates(datetime(year=2024, month=7, day=1), None). \
            submit()
