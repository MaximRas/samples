from pprint import pformat
import logging

import consts

from pages.base_page import NoElementException
from pages.widgets.value import ValueWidget
from pages.widgets.value import ValueWidgetAutorefreshException
from pages.widgets.shared import BaseSharedWidget
from pages.widgets.live_feed import LiveFeedWidget
from pages.widgets.pie_chart import PieChartWidget
from pages.widgets.line_chart import LineChartWidget
from pages.widgets.bar_chart import BarChartWidget
from pages.widgets.header import WidgetHeader


log = logging.getLogger('widgets')


class SwitchBarLineChartExeption(Exception):
    pass


class ValueShared(BaseSharedWidget, ValueWidget):
    pass


class LiveFeedShared(BaseSharedWidget, LiveFeedWidget):
    pass


class PieChartShared(BaseSharedWidget, PieChartWidget):
    pass


class LineChartShared(BaseSharedWidget, LineChartWidget):
    pass


class BarChartShared(BaseSharedWidget, BarChartWidget):
    pass


class ValueNotShared(WidgetHeader, ValueWidget):  # type: ignore[reportIncompatibleVariableOverride]
    def __init__(self, title, *args, **kwargs):
        WidgetHeader.__init__(self, title=title, *args, **kwargs)
        ValueWidget.__init__(self, *args, **kwargs)

    def disable_autorefresh(self):
        raise ValueWidgetAutorefreshException


class PieChartNotShared(WidgetHeader, PieChartWidget):  # type: ignore[reportIncompatibleVariableOverride]
    def __init__(self, title, *args, **kwargs):
        WidgetHeader.__init__(self, title=title, *args, **kwargs)
        PieChartWidget.__init__(self, *args, **kwargs)


class LineChartNotShared(WidgetHeader, LineChartWidget):  # type: ignore[reportIncompatibleVariableOverride]
    def __init__(self, title, *args, **kwargs):
        WidgetHeader.__init__(self, title=title, *args, **kwargs)
        LineChartWidget.__init__(self, *args, **kwargs)


class BarChartNotShared(WidgetHeader, BarChartWidget):  # type: ignore[reportIncompatibleVariableOverride]
    def __init__(self, title, *args, **kwargs):
        WidgetHeader.__init__(self, title=title, *args, **kwargs)
        BarChartWidget.__init__(self, *args, **kwargs)


class LiveFeedNotShared(WidgetHeader, LiveFeedWidget):  # type: ignore[reportIncompatibleVariableOverride]
    def __init__(self, title, *args, **kwargs):
        WidgetHeader.__init__(self, title=title, *args, **kwargs)
        LiveFeedWidget.__init__(self, *args, **kwargs)


NotSharedChart = (
    BarChartNotShared |
    LineChartNotShared |
    PieChartNotShared |
    ValueNotShared
)

NotSharedWidget = NotSharedChart | LiveFeedNotShared


def get_base_state(widget, is_shared):
    from tools.ico_button import IcoButton
    from pages.widgets.header import WidgetHeaderIconButton

    state = {}

    state.update(widget.root.location)
    state.update(widget.root.size)

    if not is_shared:
        state['title'] = widget.title
        state['header_buttons'] = []
        for header_btn in widget.header_buttons:
            if isinstance(header_btn, WidgetHeaderIconButton):
                state['header_buttons'].append(
                    {
                        'title': header_btn.title,
                        'is_enabled': header_btn.is_highlighted(),
                        'slug': header_btn.slug,
                        'location': header_btn.root.location,
                    }
                    
                )
            elif isinstance(header_btn, IcoButton):
                state['header_buttons'].append(
                    {
                        'slug': header_btn.name,
                        'location': header_btn._element.location,
                    }
                    
                )
            else:
                raise RuntimeError(f'Unknown widget header button class: {type(header_btn)}')
    else:
        try:
            state['autorefresh_button'] = {'is_enabled': widget._is_autorefresh_enabled()}
        except NoElementException:
            log.info(f'{widget} doesn\'t have "autorefresh" button')
        else:
            state['autorefresh_button'].update(widget.button_autorefresh.location | widget.button_autorefresh.size)

    if widget.type != consts.WIDGET_LIVE_FEED:
        state['legend'] = widget.legend_schema
        state['timeslice'] = widget.timeslice_schema

    if widget.type == consts.WIDGET_LIVE_FEED:
        state['thumbs'] = widget.grid_state
    elif widget.type == consts.WIDGET_VALUE:
        state['counter'] = {
            'value': widget.value,
            'size': widget.text_element.size,
            'loc': widget.text_element.location,
        }
    else:
        state['chart_state'] = widget.chart_state

    log.debug(f'{widget} state:\n{pformat(state)}')
    return state
