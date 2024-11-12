import logging
import time

import allure
from selenium.common.exceptions import ElementClickInterceptedException

import consts
from tools.retry import retry
from tools import wait_objects_arrive
from tools import merge_lists_in_dict
from tools.types import XPathType
from pages.button import Button
from pages.camera_picker_legacy import CameraPickerLegacy
from pages.dialog import Dialog
from pages.dropdown import DropdownOptionAlreadySet
from pages.dropdown import Select
from pages.input_field import InputFieldLegacy
from pages.input_field import CameraPickerInput
from pages.input_field import InputWithCheckboxLegacy
from pages.search.base_filters import DropdownInputFilters

log = logging.getLogger(__name__)


class BaseWidgetSettings(Dialog, DropdownInputFilters):
    """
    'Widget builder' and 'Widget settings' look similar.
    So `BaseWidgetSettings` has common functionality.
    """
    @property
    def button_filter_by_cameras(self) -> CameraPickerInput:
        return CameraPickerInput(
            x_root=self.x_root,
            label=consts.FILTER_CAMERAS_LOCATIONS,
            driver=self.driver,
            has_clear_button=True,
        )

    @property
    def input_license_plate(self) -> InputWithCheckboxLegacy:
        return InputWithCheckboxLegacy(
            label=consts.FILTER_LICENSE_PLATE,
            driver=self._driver,
            x_root=self.x_root
        )

    @property
    def input_object_name(self) -> InputWithCheckboxLegacy:
        return InputWithCheckboxLegacy(
            label=consts.FILTER_OBJECTS_NAME,
            driver=self._driver,
            x_root=self.x_root
        )

    @property
    def input_object_note(self) -> InputWithCheckboxLegacy:
        return InputWithCheckboxLegacy(
            label=consts.FILTER_OBJECTS_NOTES,
            driver=self._driver,
            x_root=self.x_root
        )

    @property
    def input_title(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label=consts.FILTER_TITLE,
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def header_title(self) -> str:
        return self.get_object(XPathType(f"({self.x_root}//p)[1]")).text

    @property
    def button_cancel(self) -> Button:
        """ Button to close builder """
        return Button(driver=self._driver, label="Cancel", x_root=self.x_root)

    @property
    def button_change_type(self) -> Button:
        """ Button to go back to Choose Widget Type dialog """
        return Button(driver=self._driver, label="CHANGE TYPE", x_root=self.x_root)

    @property
    def filter_base(self) -> Select:
        return Select(label=consts.FILTER_BASE, driver=self._driver, x_root=self.x_root)

    @property
    def button_bar_chart(self) -> Button:
        return Button(driver=self._driver, label="Bar Chart", x_root=self.x_root)

    @property
    def button_line_chart(self) -> Button:
        return Button(driver=self._driver, label="Line Chart", x_root=self.x_root)

    def set_title(self, title):
        self.input_title.type_text(title, clear_with_keyboard=True)
        return self

    def open_camera_picker(self) -> CameraPickerLegacy:
        with allure.step(f'Open "Camera/Location" filter dialog: {self}'):
            log.info(f'Open "Camera/Location" filter dialog: {self}')
            self.button_filter_by_cameras.root.click()
            time.sleep(1)
            return CameraPickerLegacy(driver=self._driver)

    def switch_to_line_chart(self):
        from pages.widgets import SwitchBarLineChartExeption

        with allure.step(f"{self}: switch type bar -> line"):
            log.info(f"{self} switch type: bar -> line")

            if not self.button_bar_chart.is_active():
                raise SwitchBarLineChartExeption('"Bar chart" button is not active')
            if self.button_line_chart.is_active():
                raise SwitchBarLineChartExeption('"Line chart" button is active')

            self.button_line_chart.click()

            if self.button_bar_chart.is_active():
                raise SwitchBarLineChartExeption('"Bar chart" button is active')
            if not self.button_line_chart.is_active():
                raise SwitchBarLineChartExeption('"Line chart" button is not active')

        return self

    def switch_to_bar_chart(self):
        from pages.widgets import SwitchBarLineChartExeption

        with allure.step(f"{self}: switch type line -> bar"):
            log.info(f"{self} switch type: line -> bar")

            if self.button_bar_chart.is_active():
                raise SwitchBarLineChartExeption('"Bar chart" button is active')
            if not self.button_line_chart.is_active():
                raise SwitchBarLineChartExeption('"Line chart" button is not active')

            self.button_bar_chart.click()

            if not self.button_bar_chart.is_active():
                raise SwitchBarLineChartExeption('"Bar chart" button is not active')
            if self.button_line_chart.is_active():
                raise SwitchBarLineChartExeption('"Line chart" button is active')

        return self

    @retry(ElementClickInterceptedException)
    def apply(self, delay=5, clickhouse_lag=True):
        """
        Widget builder - "Add widget"
        Widget settings - "Change widget"
        """
        # TODO: investigate `ElementClickInterceptedException`
        self.scroll_to_element(self.button_ok.root)
        wait_objects_arrive(clickhouse_lag=clickhouse_lag)
        self.button_ok.click()
        self.wait_disappeared()
        self.wait_spinner_disappeared()
        time.sleep(delay)  # Widget isn't ready to use immediately after creation (expecially charts)
        # All widgets may not display data immediately after creation
        # Tooltips won't show immediately after creation

    def cancel(self):
        with allure.step(f'{self}: cancel'):
            log.info(f'{self}: cancel')
            self.button_cancel.click()
            self.wait_disappeared()

    def select_base(self, base, delay=3):
        base = base.capitalize()
        with allure.step(f"{self}: select base '{base}'"):
            self.filter_base.select_option(base)
        self.wait_spinner_disappeared()
        time.sleep(delay)  # lets wait another controls
        return self

    def change_type(self):
        ''' Go back to "Choose widget type" dialog to choose another widget '''
        from pages.widgets.dialog_choose_type import ChooseWidgetType

        with allure.step(f'{self}: change widget type (go back)'):
            log.info(f'{self}: change widget type (go back)')
            self.button_change_type.click()
            self.wait_disappeared()
            return ChooseWidgetType(driver=self._driver)

    def set_filters(self, filters=None, ignore_already_selected=False, **kwargs):
        filters = filters or {}
        filters.update(kwargs)
        flags = {
            'camera_locations_has_been_cleared': False,
        }

        def _prepare_camera_loc_dialog(flags):
            dialog = self.open_camera_picker()
            if not flags['camera_locations_has_been_cleared']:
                dialog.clear_all()
                flags['camera_locations_has_been_cleared'] = True
            return dialog

        # transform `cameras`/`locations` options
        merge_lists_in_dict(filters, consts.FILTER_CAMERAS_LOCATIONS, 'cameras', 'locations')

        for filter_label, option in filters.items():

            # Although 'All' option has been changed for V2 search ('All Types', 'All Genders', etc)
            # widget builder and widget settings still use obsolete 'All' option
            if option in (consts.OPTION_ALL_VEHICLE_TYPES, consts.OPTION_ALL_GENDERS, consts.OPTION_ALL_IMAGE_QUALITY):
                option = consts.OPTION_ALL

            with allure.step(f'Set filter: "{filter_label}" -> {option}'):
                log.info(f'Set filter: "{filter_label}" -> {option}')
                if filter_label in self.inputs:
                    self.init_control(filter_label).type_text(option, clear_with_keyboard=True)
                elif filter_label in self.inputs_with_checkbox:
                    control = self.init_control(filter_label)
                    if option == '*':
                        log.warning(f'Workaround for {control}: select checkbox instead of typing "*"')
                        control.checkbox.select()
                    else:
                        control.type_text(option, clear_with_keyboard=True)
                elif filter_label == consts.FILTER_CAMERAS_LOCATIONS:
                    if not option:
                        continue
                    dialog = _prepare_camera_loc_dialog(flags)
                    for camera_or_loc_name in option:
                        if camera_or_loc_name.startswith('camera'):
                            dialog.get_camera(camera_or_loc_name).select()
                        else:
                            dialog.get_loc(camera_or_loc_name).select()
                    dialog.apply()
                elif filter_label in self.dropdowns:
                    control = self.init_control(filter_label)

                    if option.lower() != 'all' and control.value.lower() != 'all' and filter_label == consts.FILTER_VEHICLE_TYPE:
                        assert len(filters) == 1, "This workaround works if you set only one filter"
                        log.warning('Workaround for https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/292')
                        control.select_option('All')  # TODO: consider `ignore_already_selected`
                        self.apply()
                        self._parent.open_settings()

                    try:
                        control.select_option(option)
                    except DropdownOptionAlreadySet:
                        if not ignore_already_selected:
                            raise
                elif filter_label == consts.FILTER_AGE:
                    self.age_slider.set_values(*option)
                else:
                    raise RuntimeError(f"unknown filter: {filter_label}")
        return self
