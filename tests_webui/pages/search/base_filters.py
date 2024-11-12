import logging
from abc import abstractmethod

import allure

import consts
from tools.types import XPathType
from tools.retry import retry
from tools.webdriver import CustomWebDriver

from pages.base_page import PageDidNotLoaded
from pages.dropdown import Select
from pages.dropdown import Select_v0_48_4
from pages.input_field import Input_v0_48_4
from pages.input_field import InputWithCheckboxLegacy
from pages.input_field import OnlyFilledInput
from pages.input_field import CameraPickerInput
from pages.search.age_slider import AgeSlider
from pages.search.age_slider import MuiAgeSlider
from pages.search.date import InputDate

log = logging.getLogger(__name__)


class UnknownFilterException(Exception):
    pass


class DropdownInputFilters:
    """
    Common filters for:
     - Widge builder
     - Widget settings
     - Search panel
    """
    inputs = [
        consts.FILTER_TITLE,
        consts.FILTER_WATCHLIST_NAME,
        consts.FILTER_OBJECT_ID,
    ]

    inputs_with_checkbox = [
        consts.FILTER_OBJECTS_NOTES,
        consts.FILTER_OBJECTS_NAME,
        consts.FILTER_LICENSE_PLATE,
    ]

    dropdowns = [
        consts.FILTER_ORDER_BY,
        consts.FILTER_GENDER,
        consts.FILTER_IMAGE_QUALITY,
        consts.FILTER_VEHICLE_TYPE,
        consts.FILTER_BASE,
        consts.FILTER_OBJECT_TYPE,
        consts.FILTER_SEARCH_OBJECTIVE,
    ]

    multi_select = []

    @property
    @abstractmethod
    def driver(self) -> CustomWebDriver:
        raise NotImplementedError

    @property
    @abstractmethod
    def x_root(self) -> XPathType:
        raise NotImplementedError

    @property
    def input_object_note(self):
        return self.init_control(consts.FILTER_OBJECTS_NOTES)

    @property
    def input_object_name(self):
        return self.init_control(consts.FILTER_OBJECTS_NAME)

    @property
    def input_license_plate(self):
        return self.init_control(consts.FILTER_LICENSE_PLATE)

    @property
    def filter_image_quality(self):
        return self.init_control(consts.FILTER_IMAGE_QUALITY)

    @property
    def filter_gender(self):
        return self.init_control(consts.FILTER_GENDER)

    @property
    def filter_vehicle_type(self):
        return self.init_control(consts.FILTER_VEHICLE_TYPE)

    @property
    def age_slider(self):
        return MuiAgeSlider(driver=self.driver)

    @property
    @retry(UnknownFilterException, delay=2)
    def filters_schema(self):
        schema = {}
        filter_labels = [o.text for o in self.get_objects(self.x_root + "//label")]
        if not filter_labels:
            raise RuntimeError(f'{self}: no labels have been found')
        for label in filter_labels:
            if label == consts.FILTER_TITLE:
                continue
            if label == consts.FILTER_AGE:
                schema[label] = self.init_control(label).values
            else:
                schema[label] = self.init_control(label).value

        # non standard controls
        if consts.FILTER_AGE not in schema:
            try:
                schema[consts.FILTER_AGE] = self.init_control(consts.FILTER_AGE).values
            except PageDidNotLoaded:
                pass
        log.info(f'{self} filters schema: {schema}')
        return schema

    @property
    def filters_labels(self):
        return set(self.filters_schema.keys())

    def init_control(self, label, *args, **kwargs):
        # TODO: use this method to init all controls
        from pages.search.panel_v2 import LeftSearchPanel
        from pages.search.panel_v2 import RightSearchPanel
        from pages.widgets.builder import WidgetsBuilder
        from pages.widgets.settings import WidgetSettings

        klass = self.__class__.__name__
        is_search_panel = klass in (LeftSearchPanel.__name__, RightSearchPanel.__name__)
        is_widget_settings_or_builder = klass in (WidgetSettings.__name__, WidgetsBuilder.__name__)
        assert any((is_search_panel, is_widget_settings_or_builder)), f'Wrong class name: "{klass}"'
        has_clear_button = is_search_panel

        # input fields
        if label in self.inputs:
            return Input_v0_48_4(
                label=label,
                driver=self.driver,
                x_root=self.x_root,
                has_clear_button=has_clear_button,
                *args, **kwargs,
            )

        # inputs with checkbox
        elif label in self.inputs_with_checkbox:
            return (OnlyFilledInput if is_search_panel else InputWithCheckboxLegacy)(
                label=label,
                driver=self.driver,
                x_root=self.x_root,
                has_clear_button=has_clear_button,
                *args, **kwargs,
            )

        # age
        elif label == consts.FILTER_AGE:
            return (MuiAgeSlider if is_widget_settings_or_builder else AgeSlider)(
                driver=self.driver,
                x_root=self.x_root,
            )

        # dropbowns (select)
        elif label in self.dropdowns:
            return (Select_v0_48_4 if is_search_panel else Select)(
                label=label,
                driver=self.driver,
                multiselect_mode=label in self.multi_select,
                x_root=self.x_root,
                *args, **kwargs,
            )

        # camera picker
        elif label == consts.FILTER_CAMERAS_LOCATIONS:
            return CameraPickerInput(
                x_root=self.x_root,
                label=consts.FILTER_CAMERAS_LOCATIONS,
                driver=self.driver,
                has_clear_button=has_clear_button,
                *args, **kwargs,
            )

        # date picker
        elif label in (consts.FILTER_START_PERIOD, consts.FILTER_END_PERIOD):
            return InputDate(
                x_root=self.x_root,
                label=consts.FILTER_START_PERIOD,
                has_clear_button=has_clear_button,
                driver=self.driver,
                *args, **kwargs,
            )
        else:
            log.warning(f'Unknown filter: "{label}"')
            raise UnknownFilterException(label)

    def select_gender(self, gender):
        gender = gender.capitalize()
        with allure.step(f"{self}: select gender '{gender}'"):
            self.filter_gender.select_option(gender)
        return self

    def select_vehicle_type(self, vehicle_type):
        vehicle_type = vehicle_type.capitalize()
        with allure.step(f"{self}: select vehicle type '{vehicle_type}'"):
            self.filter_vehicle_type.select_option(vehicle_type)
        return self

    def set_object_note(self, text):
        with allure.step(f"{self}: set object note: '{text}'"):
            self.input_object_note.type_text(text, clear_with_keyboard=True)
        return self

    def set_object_name(self, text):
        with allure.step(f"{self}: set object name: '{text}'"):
            self.input_object_name.type_text(text, clear_with_keyboard=True)
        return self

    def set_license_plate(self, plate):
        with allure.step(f"{self}: set license plate: '{plate}'"):
            self.input_license_plate.type_text(plate, clear_with_keyboard=True)
        return self
