import logging
import time
from typing import Callable
from typing import Optional
from typing import Iterable
from abc import abstractmethod

import allure
from typing_extensions import Self
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException

import consts
from tools.retry import retry
from tools.types import XPathType
from tools.webdriver import WebElement
from pages.input_base import BaseLegacyInputField
from pages.input_base import InputTemplateLegacy
from pages.input_base import InputTemplate_v0_48_4

log = logging.getLogger(__name__)


class DropdownException(Exception):
    pass


class DropdownOptionAlreadySet(DropdownException):
    pass


class DropdownOptionNotFound(DropdownException):
    pass


class DropdownExpandException(DropdownException):
    pass


def default_match_func(value: str, option: str) -> bool:
    return value.lower() == option.lower()


class BaseDropdown(BaseLegacyInputField):
    DEFAULT_VALUES = {
        consts.FILTER_IMAGE_QUALITY: consts.SOURCE_IMG_QUALITY_GOOD,
        consts.FILTER_ORDER_BY: consts.ORDER_NEW_TO_OLD,
        consts.FILTER_GENDER: consts.OPTION_ALL_GENDERS,
        consts.FILTER_VEHICLE_TYPE: consts.OPTION_ALL_VEHICLE_TYPES,
    }

    def __init__(self, multiselect_mode: bool = False, *args, **kwargs):
        self._multiselect_mode = multiselect_mode
        super().__init__(*args, check_primary_element_timeout=10, **kwargs)
        self.default_value = self.DEFAULT_VALUES.get(self._label, consts.OPTION_ALL)

    @property
    def dropdown_element(self) -> WebElement:
        visible_ul = [ul for ul in self.get_objects(self.X_DROPDOWN_LIST) if ul.is_displayed()]
        if len(visible_ul) != 1:
            raise RuntimeError(f'Undefined dropdown (found {len(visible_ul)} visible ul elements)')
        return visible_ul[0]

    def clear_with_button(self) -> Self:
        assert self.value != self.default_value
        super().clear_with_button()
        assert self.value == self.default_value
        return self

    def _expand(self, click_method, delay=2) -> Self:
        def _has_options(get_options_method: Callable[[], Iterable[str]]) -> bool:
            options = get_options_method()
            return bool(options)

        with allure.step(f"{self}: expand"):
            log.info(f"{self}: expand")
            if self.options:
                raise DropdownExpandException(f'{self}: there are already expanded options: {self.options}')
            click_method()
            try:
                self.waiter(timeout=6, poll_frequency=2).until(lambda x: _has_options(lambda: self.options))
            except TimeoutException as exc:
                log.warning(f'{self}: there are no dropdown options')
                # self.collapse()
                raise DropdownExpandException from exc
            time.sleep(delay)
        return self

    @abstractmethod
    def expand(self) -> Self:
        raise NotImplementedError

    def collapse(self, delay=2) -> Self:
        with allure.step(f"{self}: collapse"):
            log.info(f"{self}: collapse")
            if not self.options:
                raise DropdownExpandException(f'{self}: there are no expanded options')

            # FYI: this method doesn't work for multiselect select so lets use ESC button
            # self._action_chains.move_to_element(self.root).click().perform()

            self.dropdown_element.send_keys(Keys.ESCAPE)

            try:
                self.waiter(timeout=3, poll_frequency=0.5).until(lambda x: not self.options)
            except TimeoutException as exc:
                raise DropdownExpandException from exc
            time.sleep(delay)
        return self

    @retry(StaleElementReferenceException)
    def _get_dropdown_options(self) -> Iterable[WebElement]:
        options_elements = [li for li in self.get_objects(self.X_DROPDOWN_LIST + self.X_DROPDOWN_OPTION) if li.is_displayed()]
        log.info(f' - {self} found {len(options_elements)} options')
        return options_elements

    @property
    @retry(StaleElementReferenceException)
    def options(self) -> Iterable[str]:
        '''
        UL elements which contais dropdown is outside of dialog element
        So be careful since this propety might contain wrong data
        '''
        return {option.text for option in self._get_dropdown_options()}

    def _select_option(
            self,
            option: str,
            match_func: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        if not match_func:
            match_func = default_match_func
        log.info(f"{self}: look for option '{option}'")
        elements = [e for e in self._get_dropdown_options() if match_func(e.text, option)]
        if not elements:
            raise DropdownOptionNotFound(f"{self} doesn't have option '{option}'. Available: {self.options}")
        self.scroll_to_element(elements[0])
        elements[0].click()
        time.sleep(0.5)

    def select_option(
            self,
            option: str,
            expand: bool = True,
            match_func: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        with allure.step(f"{self}: select '{option=}'"):
            if not match_func:
                match_func = default_match_func
            if match_func(self.value, option):
                raise DropdownOptionAlreadySet(option)
            if expand:
                self.expand()
            self._select_option(option, match_func=match_func)
            if self._multiselect_mode:
                log.info(f'Using multiselect mode: collapse is required: {self}')
                self.collapse()


class Select(BaseDropdown, InputTemplateLegacy):
    X_DROPDOWN_LIST = XPathType("//ul[contains(@class, 'MuiMenu-list')]")
    X_DROPDOWN_OPTION = XPathType("//li")

    @property
    def value(self) -> str:
        input_element = self.get_object(self.x_root + "//div[@aria-haspopup]")
        # textContent behaves strange: sometimes it contains capitalized string (as displayed)
        # but sometimes it contains lower-case string. So lets use 'text' attribute
        # return input_element.get_attribute("textContent")
        text = input_element.text
        # TODO: raise exeption if `text` is empty
        return text

    def expand(self, *args, **kwargs) -> Self:
        time.sleep(1)
        inner_div = self.get_object_no_wait(self.x_root + "//div[contains(@class, 'MuiSelect-selectMenu')]")
        self._expand(lambda: inner_div.click(), *args, **kwargs)
        return self


class Select_v0_48_4(BaseDropdown, InputTemplate_v0_48_4):
    X_DROPDOWN_LIST = XPathType("//div[contains(@class, 'UIDropDownItems')]")
    X_DROPDOWN_OPTION = XPathType("/div/div")

    @property
    def value(self) -> str:
        input_element = self.get_object(self.x_root + "//div[@class='input']")
        return input_element.text

    def expand(self, *args, **kwargs) -> Self:
        time.sleep(1)
        arrow_div = self.get_object_no_wait(self.x_root + "//div[contains(@class, 'arrow')]")
        self._expand(lambda: arrow_div.click(), *args, **kwargs)
        return self
