import logging
import time

import allure
from selenium.common.exceptions import TimeoutException

from consts import FILTER_AGE
from tools.retry import retry
from pages.base_page import BasePage
from pages.base_page import InvalidElementException

log = logging.getLogger(__name__)


class AgeSliderException(Exception):
    pass


class MuiAgeSlider(BasePage):
    # TODO: let's use 'Slider' class as parent
    MAX_VALUE = 100
    MIN_VALUE = 0

    def __init__(self, x_root="", *args, **kwargs):
        self.x_root = x_root + "//span[contains(@class, 'MuiSlider-root')]"
        super().__init__(min_root_opacity=0.6, *args, **kwargs)

    @property
    def slider_width(self):
        slider_rail = self.get_desc_obj("//span[@class='MuiSlider-rail']", min_opacity=0.3)
        return slider_rail.size['width']

    @property
    def thumbs(self):
        thumbs = self.get_objects(self.x_root + "//span[contains(@class, 'MuiSlider-thumb')]")

        if len(thumbs) != 2:
            raise InvalidElementException("Slider must have two thumbs!")

        left, right = thumbs

        if left.location['x'] > right.location['x']:
            left, right = right, left

        return left, right

    @property
    def values(self):
        left_thumb, right_thumb = self.thumbs
        return int(left_thumb.text), int(right_thumb.text)

    def set_values(self, left_val, right_val):
        if self.MIN_VALUE > left_val > self.MAX_VALUE or self.MIN_VALUE > right_val > self.MAX_VALUE:
            raise ValueError("Age must be within [1, 99] range!")

        def get_current_value(thumb):
            return int(thumb.get_attribute("aria-valuenow"))

        def move_thumb(thumb, value, workaround_add_value=0):
            '''
            For some reason this function gets wrong offset for the left thumb
            (though offset for the right rhumb is correct)
            Thus I add `workaround_add_value` to `value` in order to get correct offset
            '''
            if get_current_value(thumb) == value:
                log.debug(f'{self}: do not move slider: it already has value {value}')
                return
            time.sleep(0.5)
            offset_value = value - get_current_value(thumb) + workaround_add_value
            offset_px = int(self.slider_width * offset_value / (self.MAX_VALUE - self.MIN_VALUE))
            self._action_chains.click_and_hold(thumb).move_by_offset(offset_px, 0).release().perform()
            time.sleep(0.5)
            if (current_value := get_current_value(thumb)) != value:
                if workaround_add_value:
                    # workaround failed
                    raise AgeSliderException(f'{self}: wrong value after moving slider: {current_value}, expected: {value}')
                log.warning(f'{self}: wrong value after moving slider: {current_value}, expected: {value}')
                diff = value-current_value
                log.warning(f'Lets use workaround to adjust value to {diff}')
                move_thumb(thumb, value, workaround_add_value=diff)

        if left_val > right_val:
            left_val, right_val = right_val, left_val

        left_thumb, right_thumb = self.thumbs

        with allure.step(f'{self}: set values {left_val}..{right_val}'):
            log.info(f'{self}: set values {left_val}..{right_val}')

            move_thumb(left_thumb, left_val)
            move_thumb(right_thumb, right_val)


class AgeSlider(BasePage):
    # TODO: let's use 'Slider' class as parent
    MAX_VALUE = 100
    MIN_VALUE = 0

    def __init__(self, x_root="", *args, **kwargs):
        self.x_root = x_root + f"//div[label='{FILTER_AGE}']"
        super().__init__(*args, **kwargs)

    @property
    def slider_width(self):
        slider = self.get_desc_obj('//div[@class="UIRangeSlider"]')
        return slider.size['width']

    @property
    def thumbs(self):
        thumbs = self.get_objects(self.x_root + '//div[@role="slider"]')

        if len(thumbs) != 2:
            raise InvalidElementException("Slider must have two thumbs!")

        left, right = thumbs

        if left.location['x'] > right.location['x']:
            left, right = right, left

        return left, right

    @property
    def values(self):
        def get_value(thumb):
            return int(thumb.get_attribute('aria-valuenow'))

        left_thumb, right_thumb = self.thumbs
        return get_value(left_thumb), get_value(right_thumb)

    def set_values(self, left_val, right_val):
        if self.MIN_VALUE > left_val > self.MAX_VALUE or self.MIN_VALUE > right_val > self.MAX_VALUE:
            raise ValueError(f'Age must be within [{self.MIN_VALUE}, {self.MAX_VALUE}] range!')

        if left_val > right_val:
            left_val, right_val = right_val, left_val

        def get_actual_value(thumb):
            return int(thumb.get_attribute("aria-valuenow"))

        @retry(AgeSliderException)
        def move_thumb(thumb, target_value):
            offset = calc_offset(thumb, target_value)
            self._action_chains.click_and_hold(thumb).move_by_offset(offset, 0).release().perform()
            try:
                self.waiter(timeout=5, poll_frequency=1).until(
                    lambda x: get_actual_value(thumb) == target_value,
                )
            except TimeoutException as exc:
                raise AgeSliderException(
                    "Didn't manager to set value: "
                    f"{target_value} (actual: {get_actual_value(thumb)})"
                ) from exc

        def calc_offset(thumb, target_value):
            actual_value = get_actual_value(thumb)
            delta = target_value - actual_value
            offset = int(self.slider_width * delta / (self.MAX_VALUE - self.MIN_VALUE))
            log.debug(f'{self}: {actual_value=} -> {target_value=} {delta=} {offset=} slider_width={self.slider_width}')
            return offset

        with allure.step(f'{self}: set values {left_val}..{right_val}'):
            log.info(f'{self}: set values {left_val}..{right_val}')
            left_thumb, right_thumb = self.thumbs

            move_thumb(left_thumb, left_val)
            move_thumb(right_thumb, right_val)
