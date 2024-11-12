import logging
from typing import Optional

import allure

import consts
from tools.color import Color
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage

log = logging.getLogger(__name__)

ICO_UNCHECKED = IcoType('M19 5v14H5V5h14m0-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z')
ICO_UNCHECKED_GRAY = IcoType('M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10H7v-2h10v2z')
ICO_CHECKED = IcoType('M19 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.11 0 2-.9 2-2V5c0-1.1-.89-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z')
X_CHECKBOX_BUTTON = XPathType("//span[@class='MuiIconButton-label']")


class CheckboxLegacy(BasePage):
    def __init__(
            self,
            xpath: XPathType,
            name: Optional[str] = None,
            *args, **kwargs):
        self.x_root = xpath
        if name:
            self.name = name
        BasePage.__init__(self, *args, **kwargs)

    @property
    def _svg_path(self) -> IcoType:
        path_element = self.get_object(
            XPathType(self.x_root + X_CHECKBOX_BUTTON + "//*[name()='path']"))
        return IcoType(path_element.get_attribute('d'))

    @property
    def _button_check(self) -> WebElement:
        return self.get_object(XPathType(self.x_root + X_CHECKBOX_BUTTON))

    def is_checked(self) -> bool:
        # TODO: is there easier way to check??? `aria-label` attribute for example?
        if self._svg_path == ICO_CHECKED:
            return True
        if self._svg_path == ICO_UNCHECKED_GRAY:
            log.warning(f'{self.name} loc has unexpected state (unchecked gray). please resolve https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1721124466792929')
            return True
        elif self._svg_path == ICO_UNCHECKED:
            return False
        raise RuntimeError(f"Unknown state for checkbox {self.name}. svg path: {self._svg_path}")

    def switch(self) -> None:
        old_state = self.is_checked()
        with allure.step(f"{self}: switch state {old_state} -> {not old_state}"):
            log.info(f"{self}: switch state {old_state} -> {not old_state}")
            self._button_check.click()
            self.waiter(timeout=2, poll_frequency=0.1).until(
                lambda x: self.is_checked() != old_state)
            log.debug(f"{self} state changed {old_state} -> {self.is_checked()}")

    def select(self) -> None:
        with allure.step(f"{self}: select checkbox"):
            log.debug(f"{self}: select checkbox")
            if self.is_checked():
                raise RuntimeError(f"{self} already checked")
            self.switch()

    def unselect(self) -> None:
        with allure.step(f"{self}: unselect checkbox"):
            log.debug(f"{self}: unselect checkbox")
            if not self.is_checked():
                raise RuntimeError(f"{self} already unchecked")
            self.switch()


class BaseCheckbox_v0_48_4(BasePage):
    X_CHECKBOX_BUTTON = XPathType("//label[@class='UICheckBox']")

    def __init__(
            self,
            xpath: XPathType,
            name: Optional[str] = None,
            *args, **kwargs):
        self.x_root = xpath
        if name:
            self.name = name
        BasePage.__init__(self, *args, **kwargs)

    @property
    def _button_check(self) -> WebElement:
        return self.get_desc_obj(self.X_CHECKBOX_BUTTON)

    def is_checked(self) -> bool:
        checkbox_element = self.get_desc_obj(
            self.X_CHECKBOX_BUTTON + "/div",
            min_opacity=0.5
        )
        bg_color = Color(checkbox_element.value_of_css_property('background-color'))
        log.debug(f' - {self}: background color is: {bg_color}')
        default_color = Color(consts.BUTTON_BLACK_INACTIVE)
        if bg_color in (
                Color(consts.ORANGE_THEME_BUTTON_ACTIVE),
                Color(consts.BLUE_THEME_BUTTON_ACTIVE),
        ):
            return True
        if bg_color == default_color:
            return False
        raise RuntimeError(f'Unknown color: {bg_color}')

    def switch(self) -> None:
        old_state = self.is_checked()
        with allure.step(f"{self}: switch state {old_state} -> {not old_state}"):
            log.info(f"{self}: switch state {old_state} -> {not old_state}")
            self._button_check.click()
            self.waiter(timeout=2, poll_frequency=0.1).until(
                lambda x: self.is_checked() != old_state)
            log.debug(f"{self} state changed {old_state} -> {self.is_checked()}")

    def select(self) -> None:
        with allure.step(f"{self}: select checkbox"):
            log.debug(f"{self}: select checkbox")
            if self.is_checked():
                raise RuntimeError(f"{self} already checked")
            self.switch()

    def unselect(self) -> None:
        with allure.step(f"{self}: unselect checkbox"):
            log.debug(f"{self}: unselect checkbox")
            if not self.is_checked():
                raise RuntimeError(f"{self} already unchecked")
            self.switch()
