from __future__ import annotations
from typing import TYPE_CHECKING
from typing import Optional
import logging

import allure
from selenium.webdriver.remote.webelement import WebElement as WebElementOrigin

from tools import UndefinedElementException
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_elements
from tools.webdriver import find_element
if TYPE_CHECKING:
    from pages.base_page import BasePage

log = logging.getLogger(__name__)


class IcoButton:
    def __init__(self, name: str, element: WebElement):
        self._element = element
        self.name = name

    def __str__(self):
        return f'IcoButton {self.name}'

    def click(self) -> None:
        with allure.step(f'Click {self}'):
            log.info(f'Click {self}')
            self._element.click()

    def text(self) -> str:
        return self._element.text


def get_ico_button(
        page: BasePage | WebElement,
        ico: IcoType,
        button_tag: XPathType = XPathType('button'),
        ix: Optional[int] = None,
        no_button_exception=None,
        x_root: XPathType = XPathType(''),
        predicate: XPathType = XPathType(''),
        name: str = 'unknown',
        *args, **kwargs,
) -> IcoButton:
    from pages.base_page import BasePage
    from pages.base_page import NoElementException

    if button_tag[0] not in ('/', '.'):
        button_tag = XPathType(f'//{button_tag}')

    if x_root == '' and isinstance(page, BasePage):
        x_root = page.x_root

    xpath = XPathType(x_root + f"{button_tag}[{predicate} descendant::*[@d='{ico}']]")
    if isinstance(page, BasePage):
        objects = page.get_objects(xpath, *args, **kwargs)
    elif isinstance(page, WebElementOrigin):
        objects = find_elements(page, xpath, *args, **kwargs)
    else:
        raise RuntimeError

    if not objects:
        # TODO: let's use only NoButtonException
        raise no_button_exception or NoElementException(xpath)
    if ix is None and len(objects) > 1:
        raise UndefinedElementException(xpath)
    return IcoButton(name, objects[ix or 0])


def get_div_tooltip_ico_button(*args, **kwargs) -> IcoButton:
    '''
    Wrapper for `get_ico_button` for ico buttons wrappend in "div" with "Tooltip" class
    Since 0.48.4 the most ico buttons have such configuration...
    '''
    from pages.base_page import BasePage

    page = kwargs.pop('page', None)
    if page is None:
        page = args[0]
        args = args[1:]
    if isinstance(page, BasePage):
        button_tag = "div"
    elif isinstance(page, WebElementOrigin):
        button_tag = ".//div"
    else:
        raise RuntimeError(f'Unexpected page type: {type(page)}')
    return get_ico_button(
        page,
        *args,
        button_tag=button_tag,
        predicate="contains(@class, 'Tooltip') and ",
        **kwargs,
    )


def is_ico_button_active(button: IcoButton) -> bool:
    svg = find_element(button._element, XPathType("./*[name()='svg']"))
    opacity = float(svg.value_of_css_property("opacity"))
    state = None
    if opacity == 0.5:
        state = False
    if opacity == 1.0:
        state = True
    return state
