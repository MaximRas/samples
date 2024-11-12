import time
import logging
from typing import no_type_check

import allure

from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import CustomWebDriver
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog

log = logging.getLogger(__name__)

ICO_MENU = IcoType('M160-280v-30.769h456.923V-280H160Zm618-42L618.231-480.231l159.538-158L800-616 662.693-480.231l137.538 136L778-322ZM160-465.846v-30.769h343.077v30.769H160Zm0-183.385V-680h456.923v30.769H160Z')
X_CONTEXT_MENU = "//div[@class='UILocationContextMenuContent']"
NO_RESULTS = 'No results\nNot found any matches for search string'
NO_CAMERAS = 'No Cameras Detected\nCurrently you have not added any cameras. You can connect your cameras through plugin configurations'


def get_menu_button(driver: CustomWebDriver, label: str) -> Button:
    return Button(
        label=label,
        x_root=X_CONTEXT_MENU,
        is_mui=False,
        driver=driver,
    )


def get_open_menu_button(element: WebElement, button_tag: XPathType) -> IcoButton:
    ''' Cameras and locations in device tree page have the same "Menu" button '''
    return get_ico_button(
        element,
        ICO_MENU,
        x_root=XPathType(''),
        predicate="contains(@class, 'ContextMenuButton') and ",
        button_tag=button_tag,
    )


@no_type_check
def expand_spoiler(
        obj: BasePage | object,
        button: IcoButton,
        ignore_if_expanded: bool,
):
    # TODO: fix types
    if isinstance(obj, BasePage):
        page = obj
    elif isinstance(obj, object):
        page = obj._parent_page
    else:
        raise RuntimeError(f'Unknown type: {obj}')

    with allure.step(f'{obj}: expand'):
        log.info(f'{obj}: expand')
        if obj.is_expanded():
            log.info(f'{obj} is already expanded')
            if ignore_if_expanded:
                return
            raise RuntimeError(f'{obj}: unexpected state')
        button.click()
        time.sleep(1)
        page.wait(
            lambda x: obj.is_expanded(),
            custom_exception=RuntimeError(f'{obj} is still collapsed'),
            timeout=2,
            poll_frequency=0.5,
        )


@no_type_check
def collapse_spoiler(
        obj: BasePage | object,
        button: IcoButton,
        ignore_if_collapsed: bool,
):
    # type: ignore
    # TODO: fix types
    if isinstance(obj, BasePage):
        page = obj
    elif isinstance(obj, object):
        page = obj._parent_page
    else:
        raise RuntimeError(f'Unknown type: {obj}')

    with allure.step(f'{obj}: collapse'):
        log.info(f'{obj}: collapse')
        if obj.is_collapsed():
            if ignore_if_collapsed:
                return
            raise RuntimeError(f'{obj}: unexpected state')
        button.click()
        page.wait(
            lambda x: obj.is_collapsed(),
            custom_exception=RuntimeError(f'{obj} is still expanded'),
            timeout=2,
            poll_frequency=0.5,
        )
        time.sleep(1)


def create_dialog(
        obj: object,
        title: str,
        confirm_button_text: str = 'Submit') -> ConfirmDialog:
    # TODO: fix type hinting
    return ConfirmDialog(
        title=title,
        is_mui=False,
        is_mui_confirm_button=False,
        is_mui_cancel_button=False,
        has_section_message=False,
        driver=obj._parent_page.driver,  # type: ignore (Cannot access member "_parent_page" for type "object")
        confirm_label=confirm_button_text,
    )
