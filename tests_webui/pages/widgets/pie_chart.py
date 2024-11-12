from typing import Iterable
from typing import Sequence
from typing import Optional
import logging
import re
import time

from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException

import consts
from tools import are_dicts_equal
from tools import wait_objects_arrive
from tools.retry import retry
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.widgets.base_chart import BaseChartWidget
from pages.widgets.base_chart import ChangeTimesliceException

log = logging.getLogger(__name__)


class SectorNotInteractableException(Exception):
    """ Can't interact (e.g. click) with pie chart sector """


class NoTooltipException(Exception):
    pass


class NoSectorsException(Exception):
    pass


class PieChartWidget(BaseChartWidget):
    type = consts.WIDGET_PIE_CHART

    @property
    def no_data_label(self) -> Optional[WebElement]:
        return self.get_object_or_none_no_wait(
            XPathType(
                self.x_root + "//*[contains(@class, 'highcharts-no-data')]"))

    @property
    def sector_tooltip(self) -> Iterable[WebElement]:
        tooltips = self.get_objects(
            XPathType(
                self.x_root + "//*[name()='g' and contains(@class, 'highcharts-tooltip')]/*[name()='text']/*[name()='tspan']"))
        if len(tooltips) != 2:
            raise RuntimeError
        return tooltips

    @property
    def sectors(self) -> Iterable[WebElement]:
        return self.get_objects(XPathType(self.x_root + "//*[contains(@class, 'highcharts-point')]"))

    @property
    def chart_state(self) -> Sequence[dict]:
        state = []
        # NB: Sector changes its color if cursor is hovered
        for sector in self.sectors:
            tooltip = self._get_tooltip_for_sector(sector)  # get tooltip first to be sure the sector is hovered by cursor
            state.append(
                {
                    'color': sector.value_of_css_property('fill'),  # sector.get_attribute('fill'),
                    'tooltip': tooltip,
                    'location': sector.location,
                }
            )
        if not state:
            log.warning(f'{self} does not have any state (sectors)')
        return state

    @retry(StaleElementReferenceException)
    def _get_tooltip_for_sector(
            self,
            sector: WebElement,
            click_by_offset: bool = False) -> str:
        try:
            if click_by_offset:
                self._action_chains.move_to_element(sector). \
                    move_by_offset(10, 10). \
                    click(). \
                    perform()
            else:
                sector.click()
        except (ElementNotInteractableException,
                ElementClickInterceptedException):
            # TODO: may be return None???
            # TODO: add description for exceptoin
            if click_by_offset is True:
                raise SectorNotInteractableException
            else:
                log.warning(f'{self}: got SectorNotInteractableException exception. Lets click by offset')
                self._get_tooltip_for_sector(sector, click_by_offset=True)
        tooltip = ' '.join([t.text for t in self.sector_tooltip])
        if not tooltip:
            raise NoTooltipException
        log.debug(f'Pie chart tooltip text: {tooltip}')
        return tooltip

    @retry(NoTooltipException)
    @retry(SectorNotInteractableException)
    def get_tooltips(self):
        """
        Click to each pie chart sector and get its tooltip.
        Returns list of tooltips.
        Example: ["male: 3", "female: 2"]
        """
        if self.no_data_label is not None:
            log.info('Pie chart: No data to display')
            return None
        tooltips = []
        for pie_sector in self.sectors:
            tooltips.append(self._get_tooltip_for_sector(pie_sector))
        if not tooltips:
            raise NoSectorsException(self)
        return tooltips

    @staticmethod
    def parse_tooltip(tooltip: str) -> tuple[str, int]:
        attribute, amount = re.findall(r"(.+): (\d+)", tooltip)[0]
        return attribute, int(amount)

    @property
    def objects_count_list(self) -> Iterable[int]:
        """
        Returns list that contains counts of objects of each type.
        Example: [5, 2, 1, 1]
        """
        wait_objects_arrive()
        tooltips_text = self.get_tooltips()
        if tooltips_text is None:
            return [0]
        numbers = []
        for tooltip in tooltips_text:
            _, amount = self.parse_tooltip(tooltip)
            numbers.append(amount)
        log.info(f'Pie chart objects count: {numbers}')
        return numbers

    @property
    def objects_count(self) -> int:
        return sum(self.objects_count_list)

    def set_timeslice(self, *args, **kwargs):
        sectors_state = self.chart_state
        super().set_timeslice(delay=0, *args, **kwargs)
        if sectors_state:
            # if there are any bars
            try:
                self.waiter(timeout=6, poll_frequency=1).until(
                    lambda x: not are_dicts_equal(self.chart_state, sectors_state))
            except TimeoutException as exc:
                raise ChangeTimesliceException(
                    f'{self}: state has not been changed '
                    f'({self.selected_timeslice_value}): '
                    f'{args} {kwargs}') from exc
        else:
            time.sleep(5)
        return self

    def set_detalization(self, *args, **kwargs):
        raise RuntimeError('Value Widget does not have timeslice detalization')
