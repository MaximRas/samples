from logging import getLogger
from typing import Optional
from typing import Iterable
from typing import Mapping
from typing import Sequence

import allure
from typing_extensions import Self
from selenium.common.exceptions import NoSuchElementException

from consts import ICO_RIGHT_ARROW
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.steps import get_hover_tooltip
from tools.types import XPathType
from tools.types import IcoType
from tools.webdriver import WebElement
from tools.webdriver import find_element
from tools.webdriver import find_elements

from pages.base_page import BasePage
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.device_tree import collapse_spoiler
from pages.device_tree import expand_spoiler
from pages.device_tree import get_menu_button
from pages.device_tree import get_open_menu_button
from pages.device_tree import create_dialog
from pages.device_tree.add_edit_loc_dialog import AddLocDialog
from pages.device_tree.add_edit_loc_dialog import EditLocDialog
from pages.device_tree.add_cameras_dialog import AddCamerasDialog
from pages.device_tree.camera import BaseCameraWithMenu
from pages.search import NoLocationException

log = getLogger(__name__)


class BoundToLocCamera(BaseCameraWithMenu):
    def __init__(self, parent_loc, *args, **kwargs):
        self._parent_loc = parent_loc
        super().__init__(*args, **kwargs)

    @property
    def _button_remove(self) -> Button:
        '''Unbind camera from location '''
        return get_menu_button(driver=self._parent_page.driver, label='Remove camera')

    def unbind(self):
        with allure.step(f'Unbind {self} from {self._parent_loc}'):
            log.info(f'Unbind {self} from {self._parent_loc}')
            self._open_menu()
            self._button_remove.click()
            create_dialog(self, 'Remove camera'). \
                confirm()


class DeviceTreeLocation:
    def __init__(
            self,
            element: WebElement,
            parent_page: BasePage,
            parent_loc: Self,
    ):
        self._element = element
        self._parent_page = parent_page
        self._parent_loc = parent_loc

    def __str__(self):
        return self.name

    @property
    def _button_open_menu(self) -> WebElement:
        return get_open_menu_button(
            self._element,
            XPathType("./div/div[@class='UITreeLocationContent']//div")
        )

    @property
    def _button_add_sub_loc(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Add sub location')

    @property
    def _button_add_cameras(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Add cameras')

    @property
    def _button_edit(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Edit location')

    @property
    def _button_delete(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Delete location')

    @property
    def _ico_description(self) -> IcoButton:
        ICO_EXCLAMATION = IcoType('M466.077-300h30.769v-220h-30.769v220Zm13.905-274q9.018 0 15.249-5.931t6.231-15.3q0-9.45-6.214-15.571-6.213-6.121-15.23-6.121-9.787 0-15.633 6.121-5.847 6.121-5.847 15.571 0 9.369 6.214 15.3 6.213 5.931 15.23 5.931Zm.418 454q-75.176 0-140.294-28.339-65.119-28.34-114.247-77.422-49.127-49.082-77.493-114.213Q120-405.106 120-480.366q0-74.491 28.339-140.069 28.34-65.578 77.422-114.206 49.082-48.627 114.213-76.993Q405.106-840 480.366-840q74.491 0 140.069 28.339 65.578 28.34 114.206 76.922 48.627 48.582 76.993 114.257Q840-554.806 840-480.4q0 75.176-28.339 140.294-28.34 65.119-76.922 114.062-48.582 48.944-114.257 77.494Q554.806-120 480.4-120Zm.1-30.769q136.885 0 232.808-96.039 95.923-96.038 95.923-233.692 0-136.885-95.736-232.808Q617.76-809.231 480-809.231q-137.154 0-233.192 95.736Q150.769-617.76 150.769-480q0 137.154 96.039 233.192 96.038 96.039 233.692 96.039ZM480-480Z')
        return get_ico_button(
            page=self._element,
            ico=ICO_EXCLAMATION,
            button_tag=XPathType('.//div'),
            predicate="@class='Tooltip' and "
        )

    @property
    def _button_expand_collapse(self) -> IcoButton:
        return get_ico_button(
            self._element,
            ICO_RIGHT_ARROW,
            x_root=XPathType(''),
            button_tag=XPathType('./div//div'),
            predicate="@class='UITreeLocationCollapseButton' and",
        )

    def _open_menu(self) -> None:
        with allure.step(f'{self}: open menu'):
            log.info(f'{self}: open menu')
            self._button_open_menu.click()

    def is_expanded(self) -> bool:
        div_class = find_element(self._element, XPathType("./div")). \
            get_attribute('class')
        result = 'UITreeLocationOpen' in div_class
        log.debug(f'{self} is expanded: {result}')
        return result

    def is_collapsed(self) -> bool:
        return not self.is_expanded()

    def _get_childs(self) -> Iterable[BoundToLocCamera | Self]:
        childs = []
        for element_li in find_elements(self._element, XPathType("./ul/li")):
            div_class = find_element(element_li, XPathType("./div")).get_attribute('class')
            if 'UITreeLocation' in div_class:
                childs.append(
                    DeviceTreeLocation(
                        parent_page=self._parent_page,
                        element=element_li,
                        parent_loc=self,
                    )
                )
            elif 'UITreeCamera' in div_class:
                childs.append(
                    BoundToLocCamera(
                        parent_page=self._parent_page,
                        parent_loc=self,
                        element=element_li,
                    )
                )
            else:
                raise RuntimeError(f'Unexpected behavior: unknown class "{div_class}"')
        return childs

    @property
    def name(self) -> str:
        element = find_element(
            self._header,
            XPathType(".//span[contains(@class, 'UITreeLocationName')]"),
        )
        return element.text

    def _get_locations(self) -> Iterable[Self]:
        locs = []
        for child in self._get_childs():
            if isinstance(child, DeviceTreeLocation):
                locs.append(child)
        return locs

    def _get_cameras(self) -> Iterable[BoundToLocCamera]:
        cameras = []
        for child in self._get_childs():
            if isinstance(child, BoundToLocCamera):
                cameras.append(child)
        return cameras

    def expand_all_childs(self) -> None:
        with allure.step(f'Expand all child locations for {self}'):
            log.info(f'Expand all child locations for {self}')
            for loc in self._get_locations():
                loc.expand(ignore_expanded=True)
                loc.expand_all_childs()

    def get_camera(self, name: str) -> BoundToLocCamera:
        for camera in self._get_cameras():
            if camera.name == name:
                return camera
        raise RuntimeError(f'{self} no cameras with name {name}')

    def get_location(self, name: str) -> Self:
        for loc in self._get_locations():
            if loc.name == name:
                return loc
        raise NoLocationException(f'{self} no location with name {name}')

    def expand(self, ignore_expanded: bool = False) -> None:
        if self._is_empty():
            log.info(f'{self}: it is not possible to expand (location is empty)')
            return
        expand_spoiler(self, self._button_expand_collapse, ignore_expanded)

    def collapse(self, ignore_collapsed: bool = False) -> None:
        collapse_spoiler(self, self._button_expand_collapse, ignore_collapsed)

    @property
    def _header(self) -> WebElement:
        return find_element(self._element, ".//div[@class='UITreeLocationContent']")

    def _is_empty(self) -> bool:
        try:
            tag = find_element(
                self._header,
                XPathType(".//div[contains(@class, 'UITag')]"),
            ).text
        except NoSuchElementException:
            tag = None
        return tag == 'EMPTY'

    @property
    def schema(self) -> Mapping[str, Sequence | str]:
        if self._is_empty():
            expanded_sign = ''  # there is no expand/collapse button if location doesn't have any child
        else:
            expanded_sign = '▲' if self.is_expanded() else '▼'
        current_loc = f'{expanded_sign} {self.name}'.strip()

        node_schema = {current_loc: []}
        if not self.is_expanded():
            return node_schema
        for child_location in self._get_locations():
            node_schema[current_loc].append(child_location.schema)
        node_schema[current_loc].extend(sorted([c.name for c in self._get_cameras()]))
        return node_schema

    def open_delete_dialog(self) -> ConfirmDialog:
        with allure.step(f'{self}: open delete dialog'):
            log.info(f'{self}: open delete dialog')
            self._open_menu()
            self._button_delete.click()
            return create_dialog(self, 'Delete Location')

    def open_edit_dialog(self) -> EditLocDialog:
        with allure.step(f'{self}: open edit dialog'):
            log.info(f'{self}: open edit dialog')
            self._open_menu()
            self._button_edit.click()
            return EditLocDialog(driver=self._parent_page.driver)

    def get_description_tooltip(self) -> str:
        return get_hover_tooltip(self._parent_page, self._ico_description._element)

    def add_location(self, name: str, description: Optional[str] = None) -> None:
        with allure.step(f"{self}: add sub loc {name}"):
            log.info(f"{self}: add sub loc {name}")
            self._open_menu()
            self._button_add_sub_loc.click()
            dialog_add_loc = AddLocDialog(driver=self._parent_page.driver)
            dialog_add_loc.set_values(name=name, description=description)
            dialog_add_loc.confirm()

    def delete(self) -> None:
        with allure.step(f'Delete location {self}'):
            log.info(f'Delete location {self}')
            self.open_delete_dialog(). \
                confirm()

    def open_add_cameras_dialog(self) -> AddCamerasDialog:
        with allure.step(f'Open "Add cameras" dialog for {self}'):
            log.info(f'Open "Add cameras" dialog for {self}')
            self._open_menu()
            self._button_add_cameras.click()
            return AddCamerasDialog(driver=self._parent_page.driver)
