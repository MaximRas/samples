import logging
import time
from typing import Callable

import allure

import consts
from tools.types import XPathType
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button

from pages.base_page import BasePage

log = logging.getLogger(__name__)


class LeftPanel(BasePage):
    ''' Panel on the left side which is being able to hide '''
    @property
    def button_hide(self) -> IcoButton:
        return get_ico_button(
            self,
            ico=consts.ICO_HIDE_PANEL,
            button_tag=XPathType("div"),
            predicate=XPathType("contains(@class, 'UIWidgetLeftActions') and"),
        )

    def hide(self) -> None:
        with allure.step(f'Hide {self}'):
            log.info(f'Hide {self}')
            if not self.is_expanded():
                raise RuntimeError(f'{self} is not expanded')
            self.button_hide.click()
            time.sleep(2)  # skip animation
            self.wait_disappeared()

    def is_expanded(self) -> bool:
        # for semantic purposes (otherwise this method has no sense)
        root_element = self.get_object_or_none_no_wait(self.x_root)
        if not root_element:
            return False
        width = self.root.size['width']
        if width > 100:
            return True
        raise RuntimeError(f'{self}: strange width value: {width}')


def show_panel(
        show_button: IcoButton,
        panel_func: Callable[[], LeftPanel],
) -> LeftPanel:
    '''
    The problem is that LeftPanel doesn't have "show" button.
    This button is in another panel.
    Thus "LeftPanel" class doesn't have neigher "show" button nor "show" method
    '''
    with allure.step('Show left panel'):
        show_button.click()
        time.sleep(2)
        panel = panel_func()
        assert panel.is_expanded()
        panel_width = panel.root.size['width']
        window_width = panel.driver.get_window_size()['width']
        ratio = panel_width / window_width
        assert 0.1 < ratio < 0.25
        return panel
