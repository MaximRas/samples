from __future__ import annotations
from datetime import datetime
from typing import Optional
from typing import Mapping
from typing import Any
from typing import TYPE_CHECKING
import logging
import time

import allure
from selenium.common.exceptions import ElementNotInteractableException
from typing_extensions import Self

import consts
from tools import NoDataFoundException
from tools import merge_lists_in_dict
from tools import parse_object_type
from tools import wait_objects_arrive
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.retry import retry
from tools.types import XPathType

from pages.base_page import BasePage
from pages.button import Button
from pages.camera_picker_v0_48_4 import CameraPicker_v0_48_4
from pages.dropdown import DropdownOptionAlreadySet
from pages.dropdown import Select
from pages.input_field import Input_v0_48_4
from pages.input_field import CameraPickerInput
from pages.input_field import OnlyFilledInput
from pages.left_panel import LeftPanel
from pages.search.age_slider import AgeSlider
from pages.search.base_filters import DropdownInputFilters
from pages.search.date import InputDate
if TYPE_CHECKING:
    from pages.search.results_v2 import SearchResultPageV2

log = logging.getLogger(__name__)


class SearchPanelResizeException(Exception):
    pass


class BaseSearchPanelV2(BasePage, DropdownInputFilters):
    x_root = XPathType("//div[contains(@class, 'UIWidgetContainer') and descendant::div='Search filters']")

    @property
    def button_search(self) -> Button:
        return Button(
            x_root=self.x_root,
            label='Search',
            driver=self._driver,
            is_mui=False,
        )

    @property
    def age_slider(self) -> AgeSlider:
        # Builder filters and V1 search use MuiAgeSlider
        return AgeSlider(driver=self._driver, x_root=self.x_root)

    @property
    def select_order_results(self) -> Select:
        return self.init_control(consts.FILTER_ORDER_BY)

    @property
    def _ico_close(self) -> IcoButton:
        ''' V2 search doesn't have "Cancel" button any more. Instead if has close crosshair in the header '''
        return get_ico_button(self, consts.ICO_CLOSE1, button_tag='span')

    @property
    def current_base(self) -> str:
        search_objective_value = self.init_control(consts.FILTER_SEARCH_OBJECTIVE).value
        return search_objective_value.lower()

    @property
    def input_object_id(self) -> Input_v0_48_4:
        ''' FYI https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1628 '''
        return self.init_control(consts.FILTER_OBJECT_ID)

    @property
    def input_object_name(self) -> OnlyFilledInput:
        return OnlyFilledInput(
            label=consts.FILTER_OBJECTS_NAME,
            driver=self._driver,
            x_root=self.x_root,
            has_clear_button=True,
        )

    @property
    def input_object_note(self) -> OnlyFilledInput:
        return OnlyFilledInput(
            label=consts.FILTER_OBJECTS_NOTES,
            driver=self._driver,
            x_root=self.x_root,
            has_clear_button=True,
        )

    @property
    def date_from(self) -> InputDate:
        return InputDate(
            label=consts.FILTER_START_PERIOD,
            driver=self._driver,
            has_clear_button=True,
            x_root=self.x_root,
        )

    @property
    def date_to(self) -> InputDate:
        return InputDate(
            label=consts.FILTER_END_PERIOD,
            driver=self._driver,
            has_clear_button=True,
            x_root=self.x_root,
        )

    @property
    def button_filter_by_cameras_locations(self) -> CameraPickerInput:
        return CameraPickerInput(
            x_root=self.x_root,
            label=consts.FILTER_CAMERAS_LOCATIONS,
            driver=self._driver,
            has_clear_button=True,
        )

    @property
    def filtered_by(self) -> str:
        return self.button_filter_by_cameras_locations.text

    def close(self) -> None:
        with allure.step(f'{self}: close'):
            log.info(f'{self}: close')
            self._ico_close.click()
            self.wait_disappeared()

    def set_date_filter(
            self,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None) -> Self:
        def _set_date_filter(control: InputDate, date: datetime):
            control.open_filter(). \
                set_datetime(date).close()

        if date_from:
            _set_date_filter(self.date_from, date_from)
        if date_to:
            _set_date_filter(self.date_to, date_to)
        if date_from:
            # set date_from the second time
            # workaround for https://metapix-workspace.slack.com/archives/C03KJ7TM411/p1684447134223439
            _set_date_filter(self.date_from, date_from)
        return self

    def set_search_objective(self, object_type: str) -> Self:  # TODO: ImageTemplateType or 'Identification Number'
        '''
        Since 0.48.0.3893 search panel doesn't have tabs any more
        Instead of tabs it has yet another dropdown "Search objective"

        I will keep this method for sake of backward compatibility
        '''
        base = parse_object_type(object_type)[0]
        with allure.step(f"Search panel: select tab {base} (backward compatibility)"):
            log.info(f"Search panel: select tab {base} (backward compatibility)")
            try:
                self.set_filters({consts.FILTER_SEARCH_OBJECTIVE: base})
            except DropdownOptionAlreadySet:
                log.info(f'Search objective {base} has been set already')
            time.sleep(1)
            return self

    @property
    def button_clear_filters(self) -> Button:
        return Button(
            x_root=self.x_root,
            label='Clear Filters',
            driver=self._driver,
            is_mui=False,
        )

    @property
    def sort_method(self) -> str:
        return self.select_order_results.value

    def clear_filters(self) -> Self:
        ''' Clear filters also performs search '''
        with allure.step(f'{self}: clear filters'):
            log.info(f'{self}: clear filters')
            self.button_clear_filters.click()
            time.sleep(3)
        return self

    def open_camera_picker(self) -> CameraPicker_v0_48_4:
        with allure.step(f'Open "Camera/Location" filter dialog: {self}'):
            log.info(f'Open "Camera/Location" filter dialog: {self}')
            self.button_filter_by_cameras_locations.root.click()
            time.sleep(1)
            camera_picker = CameraPicker_v0_48_4(driver=self._driver)
            camera_picker.wait_spinner_disappeared(x_root=camera_picker.x_root)
            return camera_picker

    def set_filters(self, filters=None, **kwargs) -> Self:
        filters = filters or {}
        filters.update(kwargs)
        flags = {
            'camera_locations_has_been_cleared': False,
        }

        def _prepare_camera_loc_dialog(flags: Mapping[str, Any]) -> CameraPicker_v0_48_4:
            dialog = self.open_camera_picker()
            if not flags['camera_locations_has_been_cleared']:
                dialog.clear_all()
                flags['camera_locations_has_been_cleared'] = True
            return dialog

        # transform `cameras`/`locations` options
        merge_lists_in_dict(filters, consts.FILTER_CAMERAS_LOCATIONS, 'cameras', 'locations')

        for filter_label, option in filters.items():
            with allure.step(f"Set filter: {filter_label} -> {option}"):
                log.info(f"Set filter: {filter_label} -> {option}")
                if filter_label in (self.inputs + self.inputs_with_checkbox):
                    self.init_control(filter_label).type_text(option, clear_with_keyboard=True)
                elif filter_label in self.dropdowns:
                    self.init_control(filter_label).select_option(option)
                elif filter_label == consts.FILTER_CAMERAS_LOCATIONS:
                    if not option:
                        continue
                    dialog = _prepare_camera_loc_dialog(flags)
                    for camera_or_loc_name in option:
                        if camera_or_loc_name.startswith('camera'):
                            dialog.get_camera(camera_or_loc_name).select()
                        else:
                            dialog.get_loc(camera_or_loc_name).select()
                    dialog.apply()
                elif filter_label == consts.FILTER_AGE:
                    self.age_slider.set_values(*option)
                elif filter_label in ("date_from", consts.FILTER_START_PERIOD):
                    self.set_date_filter(date_from=option)
                elif filter_label in ("date_to", consts.FILTER_END_PERIOD):
                    self.set_date_filter(date_to=option)
                elif filter_label == consts.FILTER_AGE:
                    self.init_control(consts.FILTER_AGE).set_values(*option)
                else:
                    raise RuntimeError(f"unknown filter: {filter_label}")
        return self

    @retry(ElementNotInteractableException, tries=1)
    def get_results(
            self,
            fetch_more: bool = True,
            ignore_no_data: bool = False,
            ignore_error_tooltip: bool = False,
            *args, **kwargs) -> SearchResultPageV2:
        from pages.search.results_v2 import SearchResultPageV2

        log.info(f"{self}: go to search results")
        wait_objects_arrive(clickhouse_lag=False)
        with allure.step(f"{self}: go to search results"):
            self.scroll_to_element(self.button_search.root)
            self.button_search.click()
            if not ignore_error_tooltip:
                # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1410#note_73006
                self.assert_no_error_tooltips()
            # wait_spinner_disappeared is in SearchResultPageV2 contructor
            results = SearchResultPageV2(driver=self._driver, *args, **kwargs)

            if not results.thumbs and ignore_no_data is False:
                raise NoDataFoundException

            if fetch_more and results.thumbs:
                results.fetch_more()

            time.sleep(5)  # wait till pictures load (TODO: use more intelligent method to wait till all pictures load)
            return results

    def sort_by(self, order: str) -> Self:
        with allure.step(f'{self}: sort by: {order}'):
            log.info(f'{self}: sort by: {order}')
            self.select_order_results.select_option(order)
        return self


class RightSearchPanel(BaseSearchPanelV2):
    @property
    def width(self) -> int:
        return self.root.size['width']

    def resize(self, dx: int) -> Self:
        time.sleep(1)
        with allure.step(f'{self}: resize with {dx=}'):
            draggable_line = self.get_desc_obj(
                XPathType("//div[@class='react-resizable-handler']"),
                min_opacity=0.25)
            log.info(f'{self}: resize with {dx=}')
            width_before = self.width
            self._action_chains.move_to_element(draggable_line). \
                click_and_hold(). \
                move_by_offset(dx, 0). \
                release().perform()
            time.sleep(2)  # wait till the patch state request has finished
            if width_before == self.width:
                raise SearchPanelResizeException("Width hasn't been changed")
            return self


class LeftSearchPanel(LeftPanel, BaseSearchPanelV2):
    pass
