from contextlib import contextmanager
from typing import Callable
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Sequence
import logging
import time

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
import allure

import consts
from tools import NoDataFoundException
from tools import wait_objects_arrive
from tools.getlist import GetList
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_element

from pages.base_page import BasePage
from pages.base_page import NoElementException
from pages.button import Button
from pages.button import NoButtonException
from pages.object_thumbnail import ObjectThumbnail
from pages.range_slider import RangeSlider

log = logging.getLogger(__name__)


class Zoom(RangeSlider):
    step = 5


class GridItemsPage(BasePage):
    def __init__(
            self,
            x_root: Optional[XPathType] = None,
            *args, **kwargs):
        if x_root:
            self.x_root = x_root
        super().__init__(*args, **kwargs)

    @property
    def _cards_container(self) -> WebElement:
        return self.get_desc_obj(XPathType("//div[contains(@class, 'UICardsContainer')]"))

    @property
    def ids(self) -> Sequence[int]:
        # raises NoDataFoundException
        return [thumb.id for thumb in self.thumbs]

    @property
    def raw_items(self) -> Iterable[WebElement]:
        wait_objects_arrive(clickhouse_lag=False)
        try:
            return self.get_objects(XPathType(self._cards_container.xpath + "/div"), timeout=2)
        except NoElementException:
            log.warning(f'{self}: no card container')
            return []

    @property
    def thumbs(self) -> GetList[ObjectThumbnail]:
        return GetList([
            ObjectThumbnail(driver=self._driver, x_root=item.xpath)
            for item in self.raw_items
        ])

    @property
    def objects_count(self) -> int:
        return len(self.thumbs)

    @property
    def grid_state(self) -> Sequence[Mapping]:
        return [t.schema for t in self.thumbs]

    @property
    def _button_toggle_zoom(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_ZOOM_IN, button_tag=XPathType('span'))

    @property
    def _zoom_control(self) -> Zoom:
        return Zoom(
            driver=self._driver,
            x_root='',  # it now has absolute position
            predicate="and ancestor::*[@class='UITooltipOld']",
        )

    def scroll_down(self, times=2) -> None:
        def set_focus():
            if not self.thumbs:
                raise NoDataFoundException
            first_card = self.thumbs[0].root
            self._action_chains.move_to_element(first_card). \
                move_by_offset(
                    -first_card.size["width"]/2-5, 0
                ).click().perform()

        with allure.step(f"{self}: scroll down"):
            set_focus()
            while times > 0:
                log.info(f"try to scroll #{times}")
                self._scroll_down_by_end_button()
                self.wait_spinner_disappeared()
                times -= 1

    def _scroll_down_by_end_button(self) -> None:
        body = find_element(self.driver, XPathType('//body'))
        body.send_keys(Keys.END)

    def open_first(self):   # returns ObjectCard. Can't import this class
        return self.thumbs[0].open_card()

    def find(
            self,
            predicate: Callable[[ObjectThumbnail], bool],
            scroll_down: bool = False
    ) -> GetList[ObjectThumbnail]:
        if scroll_down:
            self.scroll_down()
        found_thumbs = [t for t in self.thumbs if predicate(t)]
        if not found_thumbs:
            raise RuntimeError('No objects found')

        return GetList(found_thumbs)

    @property
    def button_fetch_more(self) -> Button:
        return Button(
            x_root=self.x_root,
            label='Fetch More',
            driver=self._driver,
            is_mui=False,
        )

    @allure.step('Click "Zoom" button to toggle zoom panel')
    def _toggle_zoom(self) -> None:
        log.info('Toggle "Zoom" button')
        self._button_toggle_zoom.click()
        time.sleep(0.5)

    @property
    def scale_value(self) -> float:
        with allure.step('Getting zoom scale value'):
            log.info('Getting zoom scale value')
            with self._zoom_context() as zoom_control:
                return zoom_control.scale_value

    @contextmanager
    def _zoom_context(self):
        # TODO: type hinting
        self._toggle_zoom()
        try:
            zoom_control = self._zoom_control
            log.debug(f'Zoom value before action: {zoom_control.scale_value}')
            yield zoom_control
        finally:
            log.debug(f'Zoom value after  action: {zoom_control.scale_value}')
            self._toggle_zoom()

    def fetch_more(self, times: int = 3, ignore_no_button: bool = True) -> None:
        with allure.step(f'{self}: fetch more results {times} times'):
            results_before = self.objects_count
            if results_before < consts.DEFAULT_PGSIZE:
                log.debug('Skip fetching more objects due to: Objects count less than PGSIZE')
                return
            log.info(f'{self}: fetch more results {times} times')
            try:
                self.button_fetch_more.click()
            except StaleElementReferenceException:
                # looks like https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1557
                pass
            except NoButtonException:
                if not ignore_no_button:
                    raise
            self.wait_spinner_disappeared()
            if results_before < self.objects_count:
                if results_before % consts.DEFAULT_PGSIZE == 0:
                    # app tries to fetch more data (but there are no more objects)
                    pass
                else:
                    raise RuntimeError(f'No new objects have been loaded: {results_before}')
            objects_count_loaded = self.objects_count - results_before
            log.info(f'{self}: {objects_count_loaded} more objects have been loaded')
            if not objects_count_loaded:
                return
            if times > 1:
                return self.fetch_more(times-1)

    def scale_at(self, value: float) -> None:
        with allure.step(f'Scale thumbnails at {value}'):
            log.info(f'Scale thumbnails at {value}')
            with self._zoom_context() as zoom_control:
                zoom_control.click_at_offset(value)

    def zoom_out(self, times=1) -> float:
        with allure.step(f'Zoom out {times} times'):
            log.info(f'Zoom out {times} times')
            with self._zoom_context() as zoom_control:
                for _ in range(times):
                    zoom_control.zoom_out()
                time.sleep(2)  # wait for the request for changing user state
                return zoom_control.scale_value

    def reset_zoom(self) -> float:
        with allure.step('Reset zoom'):
            log.info('Reset zoom')
            with self._zoom_context() as zoom_control:
                zoom_control.reset_scale()
                time.sleep(0.5)
                return zoom_control.scale_value
