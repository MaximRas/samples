import logging
from typing import Optional

import allure
from selenium.webdriver.common.keys import Keys

import consts
from tools.ico_button import get_div_tooltip_ico_button
from tools.ico_button import IcoButton
from tools.types import IcoType
from tools.types import XPathType
from pages.base_page import BasePage

log = logging.getLogger(__name__)


class Dialog(BasePage):
    '''
    Close: hide dialog by clicking crossed icon in the right upper corner
    Cancel: hide dialog by clicking button in the left bottom corner

    Almost all dialogs have 'Cancel' button.
    Some of them have 'Close' icon. Use parameter 'has_close_icon' to indicate
    '''
    X_MUI_DIALOG_CONTAINER_PREDICATE = "contains(@class, 'MuiDialog-container') and not(contains(@style, 'hidden'))"

    def __init__(
            self,
            title: str,
            has_close_icon: bool = False,
            custom_x_root: Optional[XPathType] = None,
            ico_close: IcoType = consts.ICO_CLOSE0,
            is_mui: bool = True,
            has_section_message: bool = True,
            *args, **kwargs,
    ):
        self._has_section_message = has_section_message
        self._title = title
        self._has_close_icon = has_close_icon
        self._is_mui = is_mui
        if self._is_mui:
            self.x_root = XPathType(custom_x_root or f"//div[{self.X_MUI_DIALOG_CONTAINER_PREDICATE} and descendant::p='{self._title}']")
        else:
            self.x_root = XPathType(custom_x_root or f"//div[contains(@class, 'UIBasicDialog') and descendant::div='{self._title}']")
        super().__init__(*args, **kwargs)
        self._ico_close = ico_close

    @property
    def title(self) -> str:
        return self._title

    @property
    def message(self) -> str:
        if self._is_mui:
            element = self.get_desc_obj(XPathType("//div[contains(@class, 'MuiDialogContent')]"))
        else:
            xpath = "//div[contains(@class, 'UIWidgetBody')]"
            if self._has_section_message:
                xpath = f"{xpath}//div[contains(@class, 'UISectionMessage')]"
            element = self.get_desc_obj(XPathType(xpath))
        return element.text

    @property
    def ico_close(self) -> IcoButton:
        if not self._has_close_icon:
            raise NotImplementedError(f'{self} doesn\'t have close icon (check has_close_icon parameter)')
        return get_div_tooltip_ico_button(page=self, ico=self._ico_close)

    def close(self) -> None:
        # TODO: rename to -> `close_with_cross`
        with allure.step(f'Close dialog by clicking crossed icon {self}'):
            log.info(f'Close dialog by clicking crossed icon {self}')
            self.ico_close.click()
            self.wait_disappeared()

    def close_with_esc(self) -> None:
        with allure.step(f'Close dialog by pressing ESC button {self}'):
            log.info(f'Close dialog by pressing ESC button {self}')
            self.root.send_keys(Keys.ESCAPE)
            self.wait_disappeared()

    def __str__(self):
        return f'Dialog "{self.title}"'
