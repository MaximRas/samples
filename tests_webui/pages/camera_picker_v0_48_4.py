import re
import logging
import time
from contextlib import suppress

import allure

from tools import sort_list_of_dicts
from tools.getlist import GetList
from tools.locations import split_camera_loc_path
from tools.retry import retry
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import find_element

from pages.base_page import ElementIsNotClickableException
from pages.base_page import NoElementException
from pages.button import Button
from pages.button import NoButtonException
from pages.checkbox import BaseCheckbox_v0_48_4
from pages.dialog import Dialog
from pages.input_base import ElementInputException
from pages.location import Location

log = logging.getLogger(__name__)

ICO_CAMERA = IcoType('M194.62-200q-23.24 0-39.31-16.08-16.08-16.07-16.08-39.3v-449.24q0-23.23 16.08-39.3Q171.38-760 194.62-760h449.23q23.23 0 39.3 16.08 16.08 16.07 16.08 39.3v201.93l121.54-121.54v287.69L699.23-458.08v202.7q0 23.23-16.08 39.3Q667.08-200 643.85-200H194.62Z')


class LocationCheckbox_v0_48_4(BaseCheckbox_v0_48_4, Location):
    def __init__(self, xpath, *args, **kwargs):
        BaseCheckbox_v0_48_4.__init__(self, *args, xpath=xpath, **kwargs)
        # FYI: `Location`'s x_root property should not be overwritten
        Location.__init__(self, *args, xpath=xpath, camera_class=CameraCheckbox_v0_48_4, **kwargs)

    def __str__(self):
        return f"Location '{self.name}'"



class CameraCheckbox_v0_48_4(BaseCheckbox_v0_48_4):
    def __str__(self):
        return f"Camera '{self.name}'"

    @property
    def _header(self):
        return self.get_desc_obj("/div")

    @property
    def name(self):
        return self._header.text


class CameraPicker_v0_48_4(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            has_close_icon=True,
            title='Filter by Cameras / Locations',
            is_mui=False,
            **kwargs,
        )

    @property
    def button_select_all(self) -> Button:
        return Button(
            driver=self._driver,
            x_root=self.x_root,
            label='Select all',
            is_mui=False,
        )

    @property
    def button_clear_all(self) -> Button:
        return Button(
            driver=self._driver,
            x_root=self.x_root,
            label='Clear all',
            is_mui=False,
        )

    @property
    def button_apply(self) -> Button:
        return Button(
            driver=self._driver,
            x_root=self.x_root,
            label='Apply',
            is_mui=False,
        )

    @property
    def root_locs(self):
        return GetList(self._create_camera_location_objects('location'))

    @property
    def cameras(self):
        return GetList(self._create_camera_location_objects('camera'))

    @property
    def input_search(self):
        return self.get_object(self.x_root + "//input[contains(@placeholder, 'Search')]")

    @property
    def value_search(self):
        return self.input_search.get_attribute("value")

    @property
    def schema(self):
        # i can't use `set` due to loc schema is unhashable (dict)
        # so lets use `list` and sort `_schema` before return
        locations = []
        cameras = []
        for entity in self._create_camera_location_objects(entity_type=None):
            if isinstance(entity, CameraCheckbox_v0_48_4):
                cameras.append(f'{entity.name} {"☑" if entity.is_checked() else "☐"}')
            elif isinstance(entity, LocationCheckbox_v0_48_4):
                locations.append(entity.schema)
            else:
                raise RuntimeError(f'Unknown entity: {entity}')
        # FYI: sorted(locations) raises TypeError: '<' not supported between instances of 'dict' and 'dict'
        #         |
        #         v
        return sort_list_of_dicts(locations) + sorted(cameras)

    @property
    def label_selected_text(self):
        """
        Example:
        'Information\nYou have selected 1 camera'
        or
        'Error\nYou must allocate at least one camera'
        """
        info_element = self.get_desc_obj("//div[contains(@class, 'UISectionMessage')]")
        return info_element.text

    @property
    def label_selected_amount(self):
        try:
            locations = re.findall(r"(\d+) locations", self.label_selected_text)[0]
            cameras = re.findall(r"(\d+) camera", self.label_selected_text)[0]
        except IndexError:
            return {"locations": 0, "cameras": 0}
        return {
            "locations": int(locations),
            "cameras": int(cameras),
        }

    def _create_camera_location_objects(self, entity_type=None):
        '''
        entity_type: 'camera', 'location' or None
        '''
        def _is_camera(element):
            # try to distinguish camera from location
            ico = find_element(element, XPathType(".//*[name()='path']")).get_attribute("d")
            return ico == ICO_CAMERA

        objects = []
        for li_element in self.get_objects(self.x_root + "//ul[@role='list']/li"):
            if _is_camera(li_element) and entity_type != 'location':
                objects.append(CameraCheckbox_v0_48_4(xpath=li_element.xpath_list, driver=self._driver))
            if not _is_camera(li_element) and entity_type != 'camera':
                objects.append(LocationCheckbox_v0_48_4(xpath=li_element.xpath_list, driver=self._driver))

        return objects

    @retry(ElementInputException)
    def search(self, text):
        """ Clean up search input and type search query """
        with allure.step(f"{self}: search '{text}'"):
            self.clear_input(self.input_search)
            self.input_search.send_keys(text)
            time.sleep(1)
            if self.value_search != text:
                raise ElementInputException(
                    f"search input contains wrong text: '{self.value_search}'")
        return self

    def expand_all_locations(self):
        with allure.step(f"{self}: expand all locations"):
            log.info(f"{self}: expand all locations")
            for loc in self.root_locs:
                loc.expand_all_childs()
        return self

    def select_all(self):
        with allure.step(f"{self}: select all"):
            log.info(f"{self}: select all")
            with suppress(NoElementException):
                self.button_clear_all.click()
            self.button_select_all.click()
            time.sleep(1)  # only for visibility
        return self

    def clear_all(self):
        with allure.step(f"{self}: clear all"):
            log.info(f"{self}: clear all")
            try:
                self.button_select_all.click()
            except NoButtonException:
                log.warning('"Select all" button is not exist')
            except ElementIsNotClickableException:
                log.warning('"Select all" button is not clickable')
            self.button_clear_all.click()
            time.sleep(2)  # only for visibility
        return self

    def cancel(self):
        with allure.step(f"{self}: cancel"):
            log.info(f"{self}: cancel")
            self.ico_close.click()
            self.wait_disappeared()
        return self

    def apply(self, delay=6):
        with allure.step(f"{self}: apply"):
            log.info(f"{self}: apply")
            self.button_apply.click()
            self.wait_disappeared()
        time.sleep(delay)
        return self  # TODO: why self??? this dialog has been disappeared!

    def get_camera(self, path):
        ''' Get camera bound to location '''
        log.info(f"{self}: get: {path}")
        loc_path = split_camera_loc_path(path)[:-1]
        camera_name = split_camera_loc_path(path)[-1]
        if loc_path:
            loc = self.get_loc(loc_path)
            return loc.get_camera(camera_name)
        else:
            return self.cameras.get(camera_name)

    def get_loc(self, path):
        log.info(f"{self}: get: {path}")
        current_loc = None
        for loc in split_camera_loc_path(path):
            if current_loc is None:
                current_loc = self.root_locs.get(loc)
            else:
                current_loc = current_loc.get_location(loc)
        return current_loc

    def set_filters(self, filters=None, **kwargs):
        ''' Set camera/locaton '''
        filters = filters or {}
        filters.update(kwargs)
        self.clear_all()
        for filter_label, option in filters.items():
            with allure.step(f'Set filter: "{filter_label}" -> {option}'):
                log.info(f'Set filter: "{filter_label}" -> {option}')
                if filter_label == "cameras":
                    for camera in option:
                        self.get_camera(camera).select()
                elif filter_label == "locations":
                    for loc in option:
                        self.get_loc(loc).select()
                else:
                    raise RuntimeError(f"unknown filter: {filter_label}")
        return self