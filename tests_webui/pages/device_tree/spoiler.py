import logging
from typing import Iterable

from consts import ICO_RIGHT_ARROW
from tools import attribute_to_bool
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import XPathType

from pages.base_page import BasePage
from pages.device_tree import expand_spoiler
from pages.device_tree import collapse_spoiler

log = logging.getLogger(__name__)


class SpoilerCollapsedException(Exception):
    pass


class Spoiler(BasePage):
    def __init__(self, x_root, ix, *args, **kwargs):
        self.x_root = XPathType(f"({x_root}//div[@class='UISubHeaderCollapsed'])[{ix}]")
        self.x_childs = XPathType(f"({x_root}//div[@class='UISubHeaderCollapsedContent'])[{ix}]//div[@class='UITreeCamera']")
        super().__init__(*args, **kwargs)

    @property
    def _button_expand_collapse(self) -> IcoButton:
        return get_ico_button(
            self,
            ico=ICO_RIGHT_ARROW,
            button_tag=XPathType('div'),
            predicate="@role='button' and ",
            x_root=self.x_root,
        )

    @property
    def header(self) -> str:
        # There are 2 subheader elements:
        #   the first is header
        #   the second is container with cameras
        element = self.get_object_no_wait(
            XPathType(self.x_root + "/div[contains(@class, 'UISubHeader')][1]"))
        return element.text

    def get_childs(self, class_, *args, **kwargs) -> Iterable:
        if self.is_collapsed():
            raise SpoilerCollapsedException(self)
        childs = []
        for child in self.get_objects(self.x_childs):
            childs.append(class_(element=child, *args, **kwargs))
        # TODO: assert len(childs) > 0 ???
        return childs

    def is_expanded(self) -> bool:
        return attribute_to_bool(
            self._button_expand_collapse._element, 'aria-expanded') is True

    def is_collapsed(self) -> bool:
        return not self.is_expanded()

    def expand(self, ignore_expanded: bool = False) -> None:
        expand_spoiler(self, self._button_expand_collapse, ignore_expanded)

    def collapse(self, ignore_collapsed: bool = False) -> None:
        collapse_spoiler(self, self._button_expand_collapse, ignore_collapsed)
