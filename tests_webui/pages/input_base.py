import logging
from abc import abstractmethod
from typing import Optional
import time

import allure
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import ElementNotInteractableException
from typing_extensions import Self

import consts
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import XPathType
from tools.types import IcoType
from tools.retry import retry
from tools.webdriver import WebElement

from pages.base_page import NoElementException
from pages.base_page import BasePage
from pages.base_page import NoClearButtonException
from pages.base_page import is_element_exist

log = logging.getLogger(__name__)


class ElementInputException(Exception):
    """ Exception related to input fields """


class InputTemplateLegacy:
    X_TEMPLATE = '//label[text()="{label}"]/..'


class InputTemplate_v0_48_4:
    X_TEMPLATE = '//fieldset[child::legend="{label}"]'


class BaseInput(BasePage):
    def __init__(
            self,
            label: str,
            x_root: XPathType = XPathType(""),  # parent element xpath
            has_clear_button: bool = False,
            *args, **kwargs):
        self._has_clear_button = has_clear_button
        self._label = label
        self.x_root = XPathType(x_root + self.X_TEMPLATE.format(label=label))
        BasePage.__init__(self, *args, **kwargs)
        self._wait_element_rendered()
        self._wait_element_clickable()  # TODO: clickable div?? or input?

    @property
    def button_clear(self) -> IcoButton:
        button = get_ico_button(
            self,
            consts.ICO_CLOSE0,
            timeout_presence=1,
            no_button_exception=NoClearButtonException,
        )
        if not self._has_clear_button:
            raise RuntimeError(f'{self} should not have "clear" button')
        return button

    @property
    @abstractmethod
    def tooltip(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def text(self) -> str:
        text_lines = self.root.text.split('\n')
        if len(text_lines) == 0:
            raise RuntimeError
        if len(text_lines) == 1:
            return ''
        if len(text_lines) == 2:
            return text_lines[1].strip()
        raise RuntimeError

    @property
    @abstractmethod
    def value(self) -> str:
        raise NotImplementedError

    def clear_with_button(self):
        ''' Use "cross" to clear the field '''
        with allure.step(f'{self}: clear with crosshair button'):
            log.info(f'{self}: clear with crosshair button')
            self.button_clear.click()
            time.sleep(0.5)
            return self

    @abstractmethod
    def type_text(self, text: str, *args, **kwargs):
        raise NotImplementedError


class BaseLegacyInputField(BaseInput):
    def __init__(
            self,
            input_tag: XPathType = XPathType('input'),
            *args, **kwargs):
        self._input_tag = input_tag
        super().__init__(*args, **kwargs)

    @property
    def tooltip(self) -> Optional[str]:
        try:
            return self.get_object(XPathType(self.x_root + "//p")).text
        except NoElementException:
            return None

    @property
    def input(self) -> WebElement:
        return self.get_object_no_wait(self.x_root + f"//{self._input_tag}")

    @property
    def placeholder(self) -> str:
        return self.input.get_attribute('placeholder')

    @property
    def value(self) -> str:
        return self.input.get_attribute('value')

    @retry(ElementInputException)
    @retry(StaleElementReferenceException)
    def clear_with_keyboard(self) -> Self:
        ''' Clear input field with CTRL-a + DELTE buttons '''
        log.debug(f"{self}: clear")
        self.clear_input(self.input)
        time.sleep(1)
        if self.value:
            raise ElementInputException(f"Input '{self}' hasn't cleared")
        return self

    def clear_with_button(self) -> Self:
        assert self.value != ''
        super().clear_with_button()
        assert self.value == ''
        return self

    @retry(ElementNotInteractableException)
    def type_text(
            self,
            text: str,
            clear_with_keyboard: bool = False,
            type_iterative: bool = True,   # sometimes input validation makes it inpossible to insert text instantly
                                           # for example "Object Indentifier" in search panel
    ) -> Self:
        with allure.step(f"{self}: type text: '{text}'"):
            if not isinstance(text, str):
                log.warning(f'Is not a text: "{text}"')
                text = str(text)
            warn = ""
            expected_text = ''
            if clear_with_keyboard:
                self.clear_with_keyboard()
            if self.value:
                expected_text += self.value
                warn = f"(isn't empty: '{self.value}')"
            log.info(f"{self} type text: '{text}' {warn}")
            self._action_chains.move_to_element(self.root).click().perform()  # set focus
            if type_iterative:
                for char in text:
                    self.input.send_keys(char)
                    time.sleep(0.005)
            else:
                self.input.send_keys(text)
            expected_text += str(text)
            time.sleep(0.5)
            if self.value != expected_text:
                log.warn(f'{self}: actual text does not match expected: "{expected_text}"')
        return self


class BaseInputPassword(BaseLegacyInputField):
    ICO_SHOW_PASSWORD = IcoType('M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z')
    ICO_HIDE_PASSWORD = IcoType('M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z')

    def __init__(
            self,
            x_root: Optional[XPathType] = None,
            *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def eye_toggle_visibility(self) -> WebElement:
        return self.get_object(self.x_root + "//button")

    @property
    def ico(self) -> IcoType:
        path = self.get_object(self.x_root + '//*[name()="path"]').get_attribute('d')
        return IcoType(path)

    @property
    def type_of_field(self) -> str:
        return self.input.get_attribute('type')

    def show(self) -> None:
        with allure.step(f'Show password in {self}'):
            assert self.ico == self.ICO_SHOW_PASSWORD
            self.eye_toggle_visibility.click()
            time.sleep(1)
            assert self.ico == self.ICO_HIDE_PASSWORD

    def hide(self) -> None:
        with allure.step(f'Hide password in {self}'):
            assert self.ico == self.ICO_HIDE_PASSWORD
            self.eye_toggle_visibility.click()
            time.sleep(1)
            assert self.ico == self.ICO_SHOW_PASSWORD


def has_clear_button(control: BaseInput) -> bool:
    return is_element_exist(lambda: control.button_clear, NoClearButtonException)
