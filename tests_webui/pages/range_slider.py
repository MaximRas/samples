import logging
import math
import time

import allure

from consts import ICO_ZOOM_IN
from consts import ICO_ZOOM_OUT
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.button import Button

log = logging.getLogger(__name__)


class ScaleValueException(Exception):
    pass


class RangeSlider(BasePage):
    step = 0.05
    # TODO: consider min and max scale
    # TODO: check buttons are enabled/disabled

    def __init__(
            self,
            x_root: XPathType = XPathType(""),
            predicate: XPathType = XPathType(""),
            *args, **kwargs):
        self.x_root = f"{x_root}//div[contains(@class, 'UIRangeSlider') {predicate}]/../../../.."
        super().__init__(*args, **kwargs)

    @property
    def button_reset_scale(self) -> Button:
        return Button(driver=self._driver, label='Reset', is_mui=False, x_root=self.x_root)

    @property
    def scale_value(self) -> int:
        element = self.get_desc_obj("//div[@role='slider']")
        scale = element.get_attribute('aria-valuenow')
        scale = float(scale)
        if math.isnan(scale):
            raise ScaleValueException(f'Undefined scale value: {self}')
        return scale

    @property
    def button_zoom_in(self) -> IcoButton:
        return get_ico_button(self, ICO_ZOOM_IN, button_tag='span')

    @property
    def button_zoom_out(self) -> IcoButton:
        return get_ico_button(self, ICO_ZOOM_OUT, button_tag='span')

    @property
    def _slider(self) -> WebElement:
        return self.get_desc_obj("//div[contains(@class, 'UIRangeSlider')]")

    def click_at_offset(self, fraction: float) -> None:
        xoffset = self._slider.size['width'] * fraction
        with allure.step(f'{self}: click at offset {xoffset}'):
            log.info(f'{self}: click at {xoffset=} ({fraction=})')
            self._action_chains. \
                move_to_element_with_offset(self._slider, xoffset, 0). \
                click().release().perform()
            time.sleep(1)

    def zoom_in(self) -> None:
        with allure.step(f'{self}: zoom in'):
            log.info(f'{self}: zoom in')
            value_before = self.scale_value
            self.button_zoom_in.click()
            self.wait(
                lambda x: math.isclose(self.scale_value, value_before+self.step, abs_tol=0.00001),
                ScaleValueException(f'{value_before} -> {self.scale_value}'),
                timeout=2,
                poll_frequency=0.5,
            )
            time.sleep(1)

    def zoom_out(self) -> None:
        with allure.step(f'{self}: zoom out'):
            log.info(f'{self}: zoom out')
            value_before = self.scale_value
            self.button_zoom_out.click()
            self.wait(
                lambda x: math.isclose(self.scale_value, value_before-self.step, abs_tol=0.00001),
                ScaleValueException(f'{value_before} -> {self.scale_value}'),
                timeout=2,
                poll_frequency=0.5,
            )
            time.sleep(0.5)

    def reset_scale(self) -> None:
        with allure.step(f'{self}: reset scale'):
            log.info(f'{self}: reset scale')
            self.button_reset_scale.click()
            expected_value = 100
            self.wait(
                lambda x: self.scale_value == expected_value,
                ScaleValueException(f'Scale value == {self.scale_value} (should be {expected_value})'),
                timeout=2,
                poll_frequency=0.5,
            )
            time.sleep(1)
