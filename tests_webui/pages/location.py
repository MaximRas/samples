import time
import logging
from typing import Iterable
from typing import Mapping

from typing_extensions import Self

import consts
from tools.ico_button import get_ico_button
from tools.types import XPathType
from pages.base_page import BasePage
from pages.base_page import NoElementException

log = logging.getLogger(__name__)


class LocationCollapsedException(Exception):
    """ It is supposed that location is expanded but it doesn't """


class LocationExpandedException(Exception):
    """ It is supposed that location is collapsed but it doesn't """


class Location(BasePage):
    def __init__(self, xpath: XPathType, camera_class, *args, **kwargs):
        self.x_root_plus_desc = xpath
        self.x_root = self.x_root_plus_desc + '/div'
        self._camera_class = camera_class
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"Location '{self.name}'"

    @property
    def name(self) -> str:
        return self.root.text

    @property
    def cameras(self) -> Iterable:  # TODO: fix type
        if not self.is_expanded():
            raise LocationCollapsedException(self)
        cameras = []
        for camera_element in self.get_objects(self.x_root_plus_desc + "/ul/div/div/li[not(@aria-expanded)]"):
            if not camera_element.is_displayed():
                continue
            cameras.append(self._camera_class(xpath=camera_element.xpath, driver=self._driver))
        return cameras

    @property
    def locations(self) -> Iterable[Self]:
        if not self.is_expanded():
            raise LocationCollapsedException(self)
        locs = []
        for loc_element in self.get_objects(self.x_root_plus_desc + "/ul/div/div/li[@aria-expanded]"):
            locs.append(
                self.__class__(xpath=loc_element.xpath, driver=self._driver)
            )
        return locs

    def is_expanded(self) -> bool:
        try:
            get_ico_button(self, consts.ICO_EXPAND_ARROW_DOWN, button_tag='/div')
            return False
        except NoElementException:
            get_ico_button(self, consts.ICO_COLLAPSE_ARROW_UP, button_tag='/div')
            return True

    def click_header(self) -> Self:
        self.root.click()
        time.sleep(1)
        return self

    def expand(self) -> Self:
        if self.is_expanded():
            raise LocationExpandedException(self)
        self.click_header()
        self.waiter(timeout=3).until(lambda x: self.is_expanded())
        return self

    def expand_all_childs(self) -> None:
        try:
            self.expand()
            log.info(f'{self} has been expanded')
        except LocationExpandedException:
            log.info(f'Skip {self} due to LocationExpandedException')

        for loc in self.locations:
            loc.expand_all_childs()

    def collapse(self) -> None:
        if self.is_expanded() is False:
            raise LocationExpandedException(self)
        self.click_header()
        self.waiter(timeout=3).until(lambda x: self.is_expanded() is False)

    def get_camera(self, name):  # TODO: fix type
        for camera in self.cameras:
            if camera.name == name:
                return camera
        raise RuntimeError(f"Not found camera: {name}")

    def get_location(self, name) -> Self:
        from pages.search import NoLocationException

        for loc in self.locations:
            if loc.name == name:
                return loc
        raise NoLocationException(name)

    @property
    def schema(self) -> Mapping:  # TODO: fix type
        from pages.camera_picker_legacy import LocationCheckbox
        from pages.camera_picker_v0_48_4 import LocationCheckbox_v0_48_4

        expaneded_sign = '▲' if self.is_expanded() else '▼'
        current_loc = f'{expaneded_sign} {self.name}'
        if isinstance(self, (LocationCheckbox, LocationCheckbox_v0_48_4)):
            enabled_sign = '☑' if self.is_checked() else '☐'
            current_loc += f' {enabled_sign}'
        node_schema = {current_loc: []}
        if not self.is_expanded():
            return node_schema
        for child_location in self.locations:
            node_schema[current_loc].append(child_location.schema)
        for child_camera in self.cameras:
            node_schema[current_loc].append(f'{child_camera.name} {"☑" if child_camera.is_checked() else "☐"}')
        return node_schema
