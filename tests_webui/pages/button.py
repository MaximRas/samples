import time
import logging
from typing import Optional

from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import ElementNotInteractableException
import allure

import consts
from tools import attribute_to_bool
from tools.retry import retry
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import ElementIsNotClickableException
from pages.base_page import NoElementException
from pages.base_page import PageDidNotLoaded
from pages.base_page import BasePage

log = logging.getLogger(__name__)


class NoButtonException(NoElementException):
    pass


class Button(BasePage):
    COLORS_ACTIVE = [
        consts.SHARPVUE_THEME_BUTTON_ACTIVE,
        consts.SHARPVUE_THEME_BUTTON_ACTIVE_PRESSED,
        consts.ORANGE_THEME_BUTTON_ACTIVE,
        consts.ORANGE_THEME_BUTTON_ACTIVE_PRESSED,
        consts.BLUE_THEME_BUTTON_ACTIVE,
        consts.BLUE_THEME_BUTTON_ACTIVE_PRESSED,
    ]
    COLORS_INACTIVE = [
        consts.ORANGE_THEME_BUTTON_INACTIVE,
        consts.BLUE_THEME_BUTTON_INACTIVE,
        consts.BLUE_THEME_BUTTON_INACTIVE_PRESSED,
        consts.BUTTON_BLACK_INACTIVE,
    ]

    def __init__(
            self,
            label: str,
            x_root: XPathType = XPathType(""),
            is_mui: bool = True,
            *args, **kwargs,
    ):
        self._label = label
        self._is_mui = is_mui
        if self._is_mui:
            self.x_root = XPathType(x_root + f"//button[child::span='{label}']")
        else:
            self.x_root = XPathType(x_root + f"//button[text()='{label}']")

        try:
            super().__init__(min_root_opacity=0.5, *args, **kwargs)
        except PageDidNotLoaded as exc:
            raise NoButtonException(self._label) from exc

    def __str__(self):
        return f"Button '{self._label}'"

    @property
    def root(self) -> WebElement:
        try:
            return super().root
        except NoElementException as exc:
            raise NoButtonException from exc

    @property
    def bg_color(self) -> str:
        time.sleep(1)
        return self.root.value_of_css_property('background-color')

    @retry(ElementIsNotClickableException)
    def click(self) -> None:
        with allure.step(f"{self}: click"):
            self._wait_element_clickable()
            log.info(f" - {self}: click")
            try:
                self.root.click()
            except (ElementClickInterceptedException,
                    # `_wait_element_clickable` also raises ElementNotInteractableException
                    ElementNotInteractableException) as exc:
                raise ElementIsNotClickableException(self._label) from exc

    def _is_active(self) -> Optional[bool]:
        if self._is_mui:
            if self.bg_color in self.COLORS_ACTIVE:
                log.debug(f' - {self}: active state: True')
                return True
            if self.bg_color in self.COLORS_INACTIVE:
                log.debug(f' - {self}: active state: False')
                return False
            log.warning(f' - {self}: unknown state: {self.bg_color}')
            return None

        # new style button
        opacity = float(self.root.value_of_css_property('opacity'))
        is_disabled = attribute_to_bool(self.root, 'disabled')
        if opacity == 0.5 and is_disabled is True:
            return False
        if opacity == 1.0 and is_disabled is False:
            return True
        log.warning(f' - Unknown state of {self}')
        return None

    def is_active(self) -> bool:
        with allure.step(f'Check {self} is active'):
            log.info(f'Check {self} is active')
            self.wait(
                lambda x: self._is_active() is not None,
                RuntimeError(f'{self}: undefined state'),
                timeout=3,
                poll_frequency=0.5,
            )
            return self._is_active()


class IconButton(BasePage):
    def __init__(self, x_root: XPathType, title: str, *args, **kwargs):
        self.x_root = x_root
        self.title = title
        super().__init__(*args, check_primary_element_timeout=10, **kwargs)

    def __str__(self):
        return f'Button "{self.title}"'

    @retry(ElementClickInterceptedException)
    def click(self) -> None:
        with allure.step(f'Click {self}'):
            log.info(f' - Click {self}')
            self.root.click()
            time.sleep(1)
