from contextlib import suppress
import logging

import allure
import pytest

import consts
from pages.dropdown import DropdownException
from pages.widgets import ValueNotShared
from pages.widgets import BarChartNotShared
from pages.widgets import PieChartNotShared
from pages.widgets import SwitchBarLineChartExeption

from tests_webui.regression.widgets import check_legend_colors_are_different
from tests_webui.regression.widgets import restore_widget_default_timeslice_and_detalization
from tests_webui.regression.real_data import switch_2w_timeslice
from tests_webui.regression.real_data import set_custom_timeslice

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.regression,
]


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Value')
@allure.title('Ensure that values are properly formatted with thousands separators')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1066')
def test_value_widget_thousands_separator(metapix, driver):
    widget = ValueNotShared(title='Numeric Value', driver=driver)

    switch_2w_timeslice(widget.wait_spinner_disappeared())
    value_text = widget.text
    assert len(value_text) > 4  # 1k + comma
    assert value_text[-4] == ','


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/514")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/657")
@allure.title("Colors of legend's labels dedicated to various types must be different for {widget_type}")
@pytest.mark.parametrize(
    "widget_type", [
        consts.WIDGET_BAR_CHART,
        # consts.WIDGET_LINE_CHART,  # It is hard to count lots of objects in line chart
        consts.WIDGET_PIE_CHART,
    ]
)
def test_legend_colors_are_different(metapix, widget_type):
    def get_widget(widget_type):
        widget_type_to_name = {
            consts.WIDGET_BAR_CHART: 'Bar / Line Chart',
            consts.WIDGET_PIE_CHART: 'Pie Chart',
        }
        widget_type_to_class = {
            consts.WIDGET_BAR_CHART: BarChartNotShared,
            consts.WIDGET_PIE_CHART: PieChartNotShared,
        }
        widget = widget_type_to_class[widget_type](widget_type_to_name[widget_type], driver=metapix.driver)
        if widget_type == consts.WIDGET_BAR_CHART:
            with suppress(SwitchBarLineChartExeption):
                widget = widget.switch_to_bar_chart()
        return widget

    def switch_base(widget, base):
        settings = widget.open_settings()
        try:
            settings. \
                set_filters({consts.FILTER_BASE: base}). \
                apply()
        except DropdownException:
            log.warning(f'Widget already has base: {base}')
            settings.cancel()

    bases = ['vehicle', 'face']
    widget = get_widget(widget_type)

    set_custom_timeslice(widget)
    try:
        for base in bases:
            switch_base(widget, base)
            check_legend_colors_are_different(widget, base)
    finally:
        restore_widget_default_timeslice_and_detalization(widget)
