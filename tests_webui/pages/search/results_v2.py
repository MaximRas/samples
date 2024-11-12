import logging
import time
from typing import Optional

import allure
from typing_extensions import Self

import consts
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.ico_button import is_ico_button_active
from tools.types import XPathType

from pages.button import NoButtonException
from pages.grid_items import GridItemsPage
from pages.left_panel import show_panel
from pages.search.panel_v2 import LeftSearchPanel

log = logging.getLogger(__name__)


class SearchResultPageV2(GridItemsPage):
    path = '/appearances'
    x_root = XPathType("//div[child::div[child::div[text()='Search results']]]")

    def __init__(self, wait_spinner_disappeared: bool = True, *args, **kwargs):
        super().__init__(x_root=self.x_root, *args, **kwargs)
        self.x_root_action_buttons = self.x_root + "//div[@class='UIWidgetRightActions']"
        # Loader may remain in DOM even though results loaded
        if wait_spinner_disappeared:
            self.wait_spinner_disappeared()

    @property
    def button_hide_object_info(self) -> IcoButton:
        return get_ico_button(
            self,
            consts.ICO_HIDE_OBJECT_INFO,
            button_tag='span',
            x_root=self.x_root_action_buttons,
        )

    @property
    def button_roi_state(self) -> IcoButton:
        return get_ico_button(
            self,
            consts.ICO_SQUARE,
            button_tag='span',
            x_root=self.x_root_action_buttons,
        )

    @property
    def roi_state_number(self) -> int:
        return int(self.button_roi_state.text)

    @property
    def _button_show_filters(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_SHOW_PANEL, button_tag='span', no_button_exception=NoButtonException)

    def switch_roi_state(self) -> None:
        with allure.step(f'Search results: switch ROI state (current is {self.roi_state_number})'):
            log.info(f'Search results: switch ROI state (current is {self.roi_state_number})')
            prev_state = self.roi_state_number
            self.button_roi_state.click()
            self.wait(
                lambda x: self.roi_state_number != prev_state,
                poll_frequency=0.5,
                timeout=3,
            )
            time.sleep(2)  # wait till save satate request comlete

    def refresh(self) -> Self:
        super().refresh()
        self.wait_spinner_disappeared(
            comment='Wait "Searching..." loader disappered',
            x_root=self.x_root,
        )

    # @override py3.12
    def is_spinner_showing(self, *args, **kwargs) -> bool:
        spinners = self.get_objects(
            XPathType(self.x_root + "//div[descendant::*[name()='circle'] and child::div[text()='Searching...']]")
        )
        return bool(spinners)

    def _is_hide_object_info_enabled(self) -> Optional[bool]:
        # TODO: incapsulate this method with `button_hide_object_info` button
        return is_ico_button_active(self.button_hide_object_info)

    def hide_object_info(self) -> None:
        with allure.step(f'{self}: hide object info'):
            time.sleep(0.5)
            log.info(f'{self}: hide object info')
            assert self._is_hide_object_info_enabled() is True
            self.button_hide_object_info.click()
            self.waiter(timeout=3, poll_frequency=0.5).until(
                lambda x: self._is_hide_object_info_enabled() is False)
            time.sleep(2)  # wait till request completed

    def show_object_info(self) -> None:
        with allure.step(f'{self}: show object info'):
            time.sleep(0.5)
            log.info(f'{self}: show object info')
            assert self._is_hide_object_info_enabled() is False
            self.button_hide_object_info.click()
            self.waiter(timeout=3, poll_frequency=0.5).until(
                lambda x: self._is_hide_object_info_enabled() is True)
            time.sleep(2)  # wait till request completed

    @property
    def filters_panel(self) -> LeftSearchPanel:
        return LeftSearchPanel(driver=self.driver)

    def hide_filters_panel(self) -> None:
        self.filters_panel.hide()

    def show_filters_panel(self) -> LeftSearchPanel:
        show_panel(
            show_button=self._button_show_filters,
            panel_func=lambda: self.filters_panel,
        )
        return self.filters_panel
