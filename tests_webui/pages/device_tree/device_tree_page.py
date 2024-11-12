'''
Locations are created expanded by default
'''

import logging
import time
from typing import Iterable
from typing import Iterator
from typing import Mapping
from typing import Optional

import allure
from typing_extensions import Self

import consts
from tools.getlist import GetList
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.ico_button import is_ico_button_active
from tools.ico_button import get_div_tooltip_ico_button
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.base_page import NoElementException
from pages.base_page import PageDidNotLoaded
from pages.button import NoButtonException
from pages.device_tree.add_edit_loc_dialog import AddLocDialog
from pages.device_tree.camera import LeftPanelCamera
from pages.device_tree.location import BoundToLocCamera
from pages.device_tree.location import DeviceTreeLocation
from pages.input_field import SearchInput
from pages.device_tree.spoiler import Spoiler
from pages.device_tree.spoiler import SpoilerCollapsedException
from pages.ico_dialog import IcoDialog
from pages.left_panel import LeftPanel
from pages.left_panel import show_panel
from pages.search import NoLocationException

log = logging.getLogger(__name__)

ICO_ADD_ROOT_LOC = IcoType('M466.077-300h30.769v-162.923H660v-30.769H496.846V-660h-30.769v166.308H300v30.769h166.077V-300ZM480.4-120q-75.176 0-140.294-28.339-65.119-28.34-114.247-77.422-49.127-49.082-77.493-114.213Q120-405.106 120-480.366q0-74.491 28.339-140.069 28.34-65.578 77.422-114.206 49.082-48.627 114.213-76.993Q405.106-840 480.366-840q74.491 0 140.069 28.339 65.578 28.34 114.206 76.922 48.627 48.582 76.993 114.257Q840-554.806 840-480.4q0 75.176-28.339 140.294-28.34 65.119-76.922 114.062-48.582 48.944-114.257 77.494Q554.806-120 480.4-120Zm.1-30.769q136.885 0 232.808-96.039 95.923-96.038 95.923-233.692 0-136.885-95.736-232.808Q617.76-809.231 480-809.231q-137.154 0-233.192 95.736Q150.769-617.76 150.769-480q0 137.154 96.039 233.192 96.038 96.039 233.692 96.039ZM480-480Z')
ICO_OPEN_ALL_LOCS = IcoType('M180-120v-30.769h600V-120H180Zm301.231-86.154L352.308-335.077l22.23-22.231L465.846-266v-428l-91.308 91.308-22.23-22.231 128.923-128.923 128.154 128.923-22.231 22.231L496.615-694v428l90.539-91.308 22.231 22.231-128.154 128.923ZM180-809.231V-840h600v30.769H180Z')
ICO_CLOSE_ALL_LOCS = IcoType('M200-453.846v-35.385h560v35.385H200Zm0-111v-30.769h560v30.769H200ZM464.385-120v-178.769l-90.077 89.846-22-22 127.461-127.231L606-230.923l-22 22-88.846-90.615V-120h-30.769Zm15.384-571.077L352.538-818.308l22-22 88.847 89.846v-178.769h30.769v178.769l90.077-89.846 22 22-126.462 127.231Z')


class CameraGroup(Spoiler, Iterable):
    def __init__(self, get_childs_kwargs, *args, **kwargs):
        self._get_childs_kwargs = get_childs_kwargs
        super().__init__(*args, **kwargs)

    def __iter__(self) -> Iterator[LeftPanelCamera]:
        return iter(
            super().get_childs(
                LeftPanelCamera,
                **self._get_childs_kwargs
            )
        )

    def get(self, name) -> LeftPanelCamera:
        for child in self:
            if child.name == name:
                return child
        raise RuntimeError(f'{self}: no child with {name=}')


class CamerasPanel(LeftPanel):
    def __init__(self, x_root, *args, **kwargs):
        self.x_root = x_root
        super().__init__(*args, **kwargs)


class DeviceTreePage(BasePage):
    path = '/tree-view'
    x_root = XPathType("//div[child::div[text()='Locations Tree']]/../..")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._x_root_cameras = XPathType(self.x_root + "//div[contains(@class, 'UIWidgetContainer') and child::div='Cameras']")
        self._x_root_locations = XPathType(self.x_root + "//div[contains(@class, 'UIWidgetContainer') and child::div='Locations Tree']")

    @property
    def cameras_left_panel(self) -> CamerasPanel:
        return CamerasPanel(x_root=self._x_root_cameras, driver=self.driver)

    @property
    def _button_show_left_panel(self) -> IcoButton:
        return get_ico_button(
            self,
            consts.ICO_SHOW_PANEL,
            button_tag=XPathType('span'),
            no_button_exception=NoButtonException,
        )

    @property
    def _ico_add_root_loc(self) -> IcoButton:
        '''
        This is ico button located in the header of "Locations Tree"
        There is another button "Create Locatoin" which is visible if there are no locations exists
        '''
        return get_div_tooltip_ico_button(
            page=self,
            ico=ICO_ADD_ROOT_LOC,
            x_root=self._x_root_locations,
        )

    @property
    def _ico_expand_all_locs(self) -> IcoButton:
        return get_div_tooltip_ico_button(
            page=self,
            ico=ICO_OPEN_ALL_LOCS,
            x_root=self._x_root_locations,
        )

    @property
    def _ico_close_all_locs(self) -> IcoButton:
        return get_div_tooltip_ico_button(
            page=self,
            ico=ICO_CLOSE_ALL_LOCS,
            x_root=self._x_root_locations,
        )

    @property
    def _ico_show_hide_camera_information(self) -> IcoButton:
        return get_div_tooltip_ico_button(
            page=self,
            ico=consts.ICO_HIDE_OBJECT_INFO,
            x_root=self._x_root_locations,
        )

    @property
    def button_create_location(self) -> WebElement:
        '''
        This button is visible only if there is no any location exists
        '''
        return self._ico_dialog_locs.get_button_by_label('Create location')

    @property
    def input_search_camera(self) -> SearchInput:
        return SearchInput(x_root=self._x_root_cameras, driver=self.driver, label='Search')

    @property
    def input_search_location(self) -> SearchInput:
        return SearchInput(x_root=self._x_root_locations, driver=self.driver, label='Search')

    @property
    def _camera_groups(self) -> Iterable[CameraGroup]:
        # TODO: how to count all groups???!!!?? oO
        groups = []
        for i in range(10000):
            try:
                groups.append(
                    CameraGroup(
                        x_root=self._x_root_cameras,
                        ix=i+1,
                        driver=self._driver,
                        check_primary_element_timeout=5 if i == 0 else 0,
                        get_childs_kwargs=dict(parent_page=self),
                    )
                )
            except PageDidNotLoaded:
                log.debug(f'{self} found camera groups: {i}')
                break
        return groups

    def show_cameras(self) -> LeftPanel:
        return show_panel(
            show_button=self._button_show_left_panel,
            panel_func=lambda: self.cameras_left_panel,
        )

    def hide_cameras(self):
        self.cameras_left_panel.hide()

    def _get_cameras_group(self, group_name) -> CameraGroup:
        groups = tuple(filter(lambda x: x.header == group_name, self._camera_groups))
        if not groups:
            raise RuntimeError('No camera groups')
        if len(groups) > 1:
            raise RuntimeError(f'{len(groups)} groups with {group_name=}')
        return groups[0]

    @property
    def unassigned_cameras(self) -> CameraGroup:
        return self._get_cameras_group('Location Not Specified')

    @property
    def archived_cameras(self) -> CameraGroup:
        return self._get_cameras_group('Disabled')

    def _get_root_locs(self) -> GetList[DeviceTreeLocation]:
        locations = GetList()
        for loc_element in self.get_objects(
                self._x_root_locations + "//ul[contains(@class, 'UITreeLocations')]/li"):
            locations.append(
                DeviceTreeLocation(
                    element=loc_element,
                    parent_page=self,
                    parent_loc=None,
                )
            )
        return locations

    @property
    def _ico_dialog_locs(self) -> IcoDialog:
        return IcoDialog(driver=self.driver, x_root=self._x_root_locations)

    @property
    def locs_message(self) -> Optional[str]:
        '''
        Text which is displayed if there is no locations
        FYI:
         - https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1069
         - https://metapix-workspace.slack.com/archives/C05RL8G0XK6/p1694644502960349
        '''
        try:
            return self._ico_dialog_locs.text
        except PageDidNotLoaded:
            return None

    @property
    def cameras_message(self) -> Optional[str]:
        try:
            return IcoDialog(driver=self.driver, x_root=self._x_root_cameras).text
        except PageDidNotLoaded:
            return None

    @property
    def loc_schema(self) -> Mapping | str:
        _schema = {}
        for loc in self._get_root_locs():
            _schema.update(loc.schema)
        with allure.step(f'Locations schema: {_schema}'):
            log.info(f'Locations schema: {_schema}')
        if not _schema:
            _schema = self.locs_message
            # prevent error reportReturnType
            if not _schema:
                raise RuntimeError('Empty loc schema')
        return _schema

    @property
    def cameras_schema(self) -> Mapping | str:
        _schema = {}
        for group in self._camera_groups:
            try:
                cameras = tuple(group)
            except SpoilerCollapsedException:
                _schema[group.header] = 'COLLAPSED'
            else:
                _schema[group.header] = {c.name for c in cameras}
        with allure.step(f'Cameras schema: {_schema}'):
            log.info(f'Cameras schema: {_schema}')
        if not _schema:
            _schema = self.cameras_message
            # prevent error reportReturnType
            if not _schema:
                raise RuntimeError
        return _schema

    def _get_all_cameras(self) -> Iterable[LeftPanelCamera]:
        cameras = []
        for group in self._camera_groups:
            cameras.extend(group)
        return cameras

    def get_loc(self, path: str) -> DeviceTreeLocation:
        log.info(f"{self}: get location: {path}")
        current_loc = None
        for loc in path.split('>'):
            loc = loc.strip()
            if current_loc is None:
                current_loc = self._get_root_locs().get(loc)
            else:
                current_loc = current_loc.get_location(loc)
        return current_loc  # type: ignore[reportReturnType]

    def get_bound_camera(self, path: str) -> BoundToLocCamera:
        ''' Get camera bound to location '''
        log.info(f"{self}: get camera: {path}")
        loc_path = '>'.join(path.split('>')[:-1])  # all but the last
        camera_name = path.split('>')[-1].strip()
        if loc_path:
            loc = self.get_loc(loc_path)
            if not loc.is_expanded():
                raise RuntimeError(f'You are trying to look for bound camera in collapsed location: {loc}')
            return loc.get_camera(camera_name)
        # return self._get_all_cameras().get(camera_name)
        raise RuntimeError('Undefined behavior')

    def add_root_loc(self, name: str, description: Optional[str] = None) -> None:
        with allure.step(f"{self}: add root location: {name}"):
            log.info(f"{self}: add root location: {name}")
            self._ico_add_root_loc.click()
            dialog_add_loc = AddLocDialog(driver=self.driver)
            dialog_add_loc.set_values(name=name, description=description)
            dialog_add_loc.confirm()

    def add_nested_loc(self, path: str) -> None:
        with allure.step(f"{self}: add location: {path}"):
            log.info(f"{self}: add location: {path}")
            current_loc = None
            for loc_name in path.split('>'):
                loc_name = loc_name.strip()
                if current_loc is None:  # root loc
                    try:
                        current_loc = self._get_root_locs().get(
                            loc_name,
                            exception=NoLocationException,
                        )
                    except NoLocationException:
                        self.add_root_loc(loc_name)
                        current_loc = self._get_root_locs().get(loc_name)
                else:
                    try:
                        current_loc = current_loc.get_location(loc_name)
                    except NoLocationException:
                        current_loc.add_location(loc_name)
                        current_loc = current_loc.get_location(loc_name)

    def search_camera(
            self,
            query: str,
            delay: int = 2,
            clear_with_keyboard: bool = True):
        with allure.step(f"{self}: search cameras: {query}"):
            log.info(f"{self}: search cameras: {query}")
            self.input_search_camera.type_text(query, clear_with_keyboard=clear_with_keyboard)
            time.sleep(delay)
        return self

    def search_loc(
            self,
            query: str,
            delay: int = 2):
        with allure.step(f"{self}: search locations: {query}"):
            log.info(f"{self}: search locations: {query}")
            self.input_search_location.type_text(query, clear_with_keyboard=True)
            time.sleep(delay)
        return self

    def expand_all_locations(self):
        with allure.step("Expand all locations"):
            log.info("Expand all locations")
            self._ico_expand_all_locs.click()
            time.sleep(1.5)
        return self

    def expand_all_locations_manually(self):
        with allure.step("Expand all locations (manually,recursive)"):
            log.info("Expand all locations (manually,recursive)")
            for loc in self._get_root_locs():
                loc.expand(ignore_expanded=True)
                loc.expand_all_childs()
            time.sleep(1.5)
        return self

    def collapse_all_locations(self):
        with allure.step("Collapse all locations"):
            log.info("Collapse all locations")
            self._ico_close_all_locs.click()
            time.sleep(1.5)
        return self

    def get_location_expanding_button_state(self) -> Optional[str]:
        with allure.step("Get button location expanding/collapsing state"):
            log.info("Get button location expanding/collapsing state")
            # TODO: refactoring is required
            try:
                if self._ico_expand_all_locs:
                    return 'Open all locations'
            except NoElementException as e:
                log.info(f'There no button error: {e}')
            try:
                if self._ico_close_all_locs:
                    return 'Close all locations'
            except NoElementException as e:
                log.info(f'There no button error: {e}')

    def show_camera_info(self) -> Self:
        with allure.step('Show camera information'):
            if is_ico_button_active(self._ico_show_hide_camera_information) is True:
                raise RuntimeError('"Show camera information": unexpected state')
            self._ico_show_hide_camera_information.click()
            time.sleep(1)
            return self

    def hide_camera_info(self) -> Self:
        with allure.step('Hide camera information'):
            if is_ico_button_active(self._ico_show_hide_camera_information) is False:
                raise RuntimeError('"Hide camera information": unexpected state')
            self._ico_show_hide_camera_information.click()
            time.sleep(1)
            return self
