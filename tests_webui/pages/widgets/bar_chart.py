import time
import re
import logging
from itertools import groupby
from functools import reduce
from typing import Iterable
from typing import Sequence
from typing import Mapping
from typing import Optional
from typing import Set

from selenium.common.exceptions import StaleElementReferenceException

import consts
from tools import are_dicts_equal
from tools.retry import retry
from tools import wait_objects_arrive
from tools.color import Color
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_elements

from pages.base_page import NoElementException
from pages.widgets.base_chart import ADJUST_MENU_COLUMN_LABEL
from pages.widgets.base_chart import BaseBarLineChartWidget
from pages.widgets.base_chart import LegendButton

log = logging.getLogger(__name__)


class BadNumberException(Exception):
    pass


class BarRect:
    def __init__(self, element: WebElement, parent):
        self._element = element
        self._parent = parent

    def __str__(self) -> str:
        return f'Rect at x:{self.x}'

    @property
    def x(self) -> float:
        return float(self._element.get_attribute("x"))

    @property
    def y(self) -> float:
        return float(self._element.get_attribute("y"))

    @property
    def width(self) -> int:
        return int(self._element.get_attribute("width"))

    @property
    def height(self) -> int:
        return int(self._element.get_attribute("height"))

    @property
    def color(self) -> Color:
        return Color(self._element.value_of_css_property("fill"))

    @property
    def legend(self) -> LegendButton:
        for legend in self._parent.legend:
            if legend.color == self.color:
                return legend
        raise RuntimeError(f"{self}: no legend found")

    @property
    def legend_title(self) -> str:
        return self.legend.name

    def is_visible(self) -> bool:
        return self.height != 0

    @property
    def tooltip(self) -> Sequence[str]:
        if not self.is_visible():
            raise RuntimeError(f"{self}: rect is hidden")

        self._parent._action_chains.move_to_element(self._element).perform()
        return self._get_tooltip_text()

    @retry(NoElementException, delay=0.5, tries=2)
    @retry(StaleElementReferenceException, delay=0.5, tries=2)
    def _get_tooltip_text(self) -> Sequence[str]:
        tooltip = self._parent.get_desc_obj(
            "//*[name()='g' and @visibility='visible' and "
            "contains(@class, 'highcharts-tooltip')]/*[name()='text']")
        if not tooltip:
            raise RuntimeError(f'{self}: no tooltip')
        lines = find_elements(tooltip, XPathType("./*[name()='tspan']"))
        assert len(lines) == 6
        text = [f'{lines[ix*2].text} {lines[ix*2+1].text}' for ix in range(3)]
        return text

    @property
    def objects_count(self) -> int:
        counter = int(re.findall(r": (\d+)", self.tooltip[-1])[0])
        return counter


class BarRectGroup:
    def __init__(self, rects: Iterable[BarRect]):
        self._rects = tuple(rects)

    def __str__(self) -> str:
        return f"Rect Group of {len(self)} rects at x:{self.x}"

    @property
    def x(self) -> Optional[float]:
        if self._rects:
            return self._rects[0].x

    @property
    def legend_titles(self) -> Set[str]:
        return {rect.legend_title for rect in self._rects}

    @property
    def objects_count(self) -> int:
        """ Objects count: summ of objects from rect's tooltips """
        counter = reduce(lambda x, y: x*y.objects_count, self._rects, 1)
        log.info(f"{self}: has {counter} objects")
        return counter

    @property
    def stack_counter(self):
        """
        Objects count: number under bar
        Thre is a problem. Rects and its stack counter are in diferent DOM branches
        So it is hard to find corresponding stack counter
        """
        raise NotImplementedError

    def __len__(self):
        return len(self._rects)


class BarChartWidget(BaseBarLineChartWidget):
    type = consts.WIDGET_BAR_CHART

    @property
    def _stack_counters(self) -> Iterable[WebElement]:
        return self.get_objects(
            XPathType(
                self.x_root +
                '//*[@class="highcharts-stack-labels"]/'
                '*[name()="g"]/*[name()="text"]/*[name()="tspan"][1]'))

    @property
    def _all_rects(self) -> Iterable[BarRect]:
        all_rects = [
            BarRect(element, self) for element in
            self.get_objects(
                XPathType(
                    self.x_root +
                    "//*[@class='highcharts-series-group']//"
                    "*[name()='rect' and contains(@class, 'highcharts-point')]"))
        ]
        return sorted(all_rects, key=lambda rect: rect.x)  # `groupby` works only with sorted data

    @property
    def chart_state(self) -> Sequence[Mapping]:
        def _tooltip_is_equal(rect: Mapping, expected_tooltip: str) -> bool:
            tooltip_date_to = rect['tooltip'][1]
            if not tooltip_date_to.startswith('To'):
                return False
            return tooltip_date_to == expected_tooltip

        def _delete_tooltip_from_rect(rect: Mapping) -> str:
            assert rect['tooltip'][1].startswith('To')
            tooltip = rect['tooltip'][1]
            log.debug(f'Delete: {rect["tooltip"][1]}')
            del rect['tooltip'][1]
            return tooltip

        rect_groups = []
        for bar in self.bars:
            rect_groups.append([])
            for rect in bar._rects:
                rect_groups[-1].append(
                    {
                        'tooltip': rect.tooltip,
                        'color': str(rect.color),
                        'size': rect._element.size,
                        'location': rect._element.location,
                    }
                )

        # workaround: the last bar tooltips is always changed (Second line: 'To...')
        # so lets delete this line
        tooltip_to_delete: str = ''  # prevent error reportPossiblyUnboundVariable
        if rect_groups:
            for rect in rect_groups[-1]:
                tooltip_to_delete = _delete_tooltip_from_rect(rect)

            # FYI: workaround for faces. faces bar chart may have 3 bar groups
            # with tooltips to delete: undefined, male, female
            for group in rect_groups:
                for rect in group:
                    if _tooltip_is_equal(rect, tooltip_to_delete):
                        _delete_tooltip_from_rect(rect)
        else:
            log.warning(f'{self} does not have any state (bars)')
        return rect_groups

    @property
    @retry(StaleElementReferenceException, delay=0.2, tries=2)
    def rects(self) -> Iterable[BarRect]:
        """ Only visible rects """
        return [rect for rect in self._all_rects if rect.is_visible()]

    @property
    def bars(self) -> Iterable[BarRectGroup]:
        grouped_by_coord = groupby(self.rects, lambda g: g.x)
        groups = []
        for x_coord, grouped_by_bar in grouped_by_coord:
            groups.append(BarRectGroup(grouped_by_bar))
            log.debug(f"{self}: group x:{x_coord} has {len(groups[-1])} rects")
        log.info(f"{self}: found {len(groups)} groups")
        return groups

    @property
    @retry(StaleElementReferenceException, delay=3)
    def objects_count_list(self) -> Iterable[int]:
        wait_objects_arrive()
        stacks_counter = []
        for counter_element in self._stack_counters:
            try:
                counter_text = re.sub(r'( )+', '', counter_element.text)
                stacks_counter.append(int(counter_text))
            except ValueError:
                stacks_counter.append(0)
        log.info(f"{self}: non-zero stacks: {[s for s in stacks_counter if s]}")
        return stacks_counter

    @property
    def objects_count(self) -> int:
        return sum(self.objects_count_list)

    def disable_column_labels(self):
        self._change_adjust_menu(ADJUST_MENU_COLUMN_LABEL, False)

    def enable_column_labels(self):
        self._change_adjust_menu(ADJUST_MENU_COLUMN_LABEL, True)

    def set_timeslice(self, *args, **kwargs):
        bars_state = self.chart_state
        super().set_timeslice(delay=0, *args, **kwargs)
        if bars_state:
            # if there are any bars
            self.waiter(timeout=5, poll_frequency=1).until(
                lambda x: not are_dicts_equal(self.chart_state, bars_state))
        else:
            time.sleep(5)
        return self

    def set_detalization(self, *args, **kwargs):
        bars_state = self.chart_state
        super().set_detalization(delay=0, *args, **kwargs)
        if bars_state:
            self.waiter(timeout=5, poll_frequency=1).until(
                lambda x: not are_dicts_equal(self.chart_state, bars_state))
        else:
            time.sleep(5)
        return self
