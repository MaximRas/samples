from collections import defaultdict
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Sequence
import logging
import time

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from typing_extensions import Self

import consts
from tools import NoDataFoundException
from tools import are_dicts_equal
from tools import wait_objects_arrive
from tools.retry import retry
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.widgets.base_chart import BaseBarLineChartWidget

log = logging.getLogger(__name__)


class LineChartException(Exception):
    pass


class NoTooltipException(LineChartException):
    pass


class Line(BasePage):
    def __init__(self, parent: BasePage, xpath: XPathType):
        self.x_root = xpath
        self._parent = parent
        super().__init__(driver=self._parent._driver)

    @property
    def root(self) -> WebElement:
        return self.get_object(self.x_root, wait_rendered=False)

    @property
    def points(self) -> Iterable[WebElement]:
        return self.get_objects(self.x_root + '/*[name()="path" and @class="highcharts-point"]')

    @retry(NoTooltipException, tries=4)
    @retry(StaleElementReferenceException, tries=3)
    def _get_tooltip_for_point(self, point: WebElement) -> str:
        ActionChains(self._driver).move_to_element(point).perform()
        tooltip_lines = self.get_objects(self._parent.x_root + "//*[name()='g' and contains(@class, 'highcharts-tooltip')]/*[name()='text']/*[name()='tspan']")
        tooltip_lines = tuple(filter(lambda t: t.is_displayed(), tooltip_lines))
        if not tooltip_lines:
            raise NoTooltipException("no tooltip found")
        assert len(tooltip_lines) == 6
        if tuple(line for line in tooltip_lines if not line):
            raise NoTooltipException(f'There are empty lines: {tooltip_lines}')
        text = [f'{tooltip_lines[ix*2].text} {tooltip_lines[ix*2+1].text}' for ix in range(3)]
        return text

    @property
    def objects_count_list(self) -> Iterable[int]:
        # button_outside = self._parent.button_detalization
        area_outside = self._parent._get_timeslice_button_by_value("Custom")

        def _move_pointer_out() -> None:
            ActionChains(self._driver).move_to_element(area_outside).perform()

        def _get_counter_from_point(point: WebElement) -> int:
            tooltip = self._get_tooltip_for_point(point)
            log.debug(f"parse tooltip: {tooltip}")
            if not tooltip:
                raise NoTooltipException

            objects_count_text = tooltip[-1].strip()
            if not objects_count_text:
                raise NoTooltipException
            objects_count = objects_count_text.split(': ')[-1]
            return int(objects_count)

        numbers_from_tooltips = []
        _move_pointer_out()  # Line chart has opacity 0.2 if hovered
        for point in self.points:
            # get the cache according to root y coord (widget had been moved???)
            root_y_location = self.root.location['y']
            cache_y_to_count = self._parent._cache[root_y_location]

            y_location = point.location['y']
            if y_location in cache_y_to_count:
                numbers_from_tooltips.append(cache_y_to_count[y_location])
            else:
                objects_count = _get_counter_from_point(point)
                numbers_from_tooltips.append(objects_count)
                cache_y_to_count[y_location] = objects_count
                log.debug(f'New cache entry: {y_location} -> {objects_count}')
        log.debug(f"{self}: {numbers_from_tooltips}")
        _move_pointer_out()
        return numbers_from_tooltips

    @property
    def objects_count(self) -> int:
        return sum(self.objects_count_list)


class LineChartWidget(BaseBarLineChartWidget):
    type = consts.WIDGET_LINE_CHART
    X_LINE_TMPL = "//*[contains(@class, 'highcharts-series-{chart_ind} ') " \
        "and contains(@class, 'highcharts-markers')]"

    def __init__(self, *args, **kwargs):
        self._cache: Mapping[int, Mapping[int, int]] = defaultdict(dict)
        super().__init__(*args, **kwargs)

    @property
    def _lines(self) -> Iterable[Line]:
        # TODO: each line should have a name. i.e. "Male 20-30", "Female other", etc
        wait_objects_arrive()
        line_ix = 0
        lines = []
        while True:
            line_element = self.get_object_or_none_no_wait(self.x_root + self.X_LINE_TMPL.format(chart_ind=line_ix))
            if line_element is None:
                break
            lines.append(Line(self, self.x_root + self.X_LINE_TMPL.format(chart_ind=line_ix)))
            line_ix += 1
        if not lines:
            raise NoDataFoundException
        if self._cache:
            size = 0
            for y_root_loc in self._cache:
                size += len(self._cache[y_root_loc])
            log.warning(f'Clear cache {size=} for {self}')
            self._cache.clear()
        return lines

    @property
    def chart_state(self) -> Sequence[dict[str, Any]]:
        state = []
        for line in self._lines:
            state.append(
                {
                    'color': line.points[0].get_attribute('fill'),
                    'points': [],
                    'objects_count': line.objects_count_list,
                }
            )
            for point in line.points:
                state[-1]['points'].append(
                    {
                        'location': point.location,
                    }
                )
        if not state:
            log.warning(f'{self} does not have any state (lines)')
        return state

    @property
    @retry(LineChartException)
    def _objects_count_list(self) -> Iterable[int]:
        wait_objects_arrive()
        _objects_count = [0] * len(self.labels_x)
        for ix, line in enumerate(self._lines):
            log.info(f'Getting objects count for line #{ix+1} of {len(_objects_count)}')
            if len(line.objects_count_list) != len(_objects_count):
                raise LineChartException(f'Points on line: {len(line.objects_count_list)} but '
                                         f'amount of x-labels: {len(_objects_count)}')
            for ix, amount in enumerate(line.objects_count_list):
                try:
                    _objects_count[ix] += amount
                except IndexError as exc:
                    raise LineChartException(
                        f'Point index: {ix}. Expected points: {len(_objects_count)}'
                    ) from exc
        log.info(f"{self}: {_objects_count}")
        return _objects_count

    @property
    def objects_count(self) -> int:
        return sum(self._objects_count_list)

    def set_timeslice(self, *args, **kwargs) -> Self:
        try:
            lines_state = self.chart_state
        except NoDataFoundException:
            lines_state = None
        super().set_timeslice(delay=0, *args, **kwargs)
        if lines_state:
            self.waiter(timeout=5, poll_frequency=1).until(
                lambda x: not are_dicts_equal(self.chart_state, lines_state))
        else:
            time.sleep(5)
        return self

    def set_detalization(self, *args, **kwargs) -> Self:
        lines_state = self.chart_state
        super().set_detalization(delay=0, *args, **kwargs)
        if lines_state:
            self.waiter(timeout=5, poll_frequency=1).until(
                lambda x: not are_dicts_equal(self.chart_state, lines_state))
        else:
            time.sleep(5)
        return self
