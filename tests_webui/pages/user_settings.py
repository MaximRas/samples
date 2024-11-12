import time
import logging
from typing import Optional

import allure
from typing_extensions import Self

import consts
from tools.ico_button import get_div_tooltip_ico_button
from tools.ico_button import IcoButton
from tools.time_tools import TimeZone
from tools.time_tools import date_to_str
from tools.time_tools import now_pst
from tools.time_tools import is_12h_time_format
from tools.types import XPathType
from tools.types import StrDateType
from tools.types import DateTimeFormatType
from tools.webdriver import WebElement
from tools.webdriver import find_element

from pages.base_page import BasePage
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.dropdown import Select_v0_48_4
from pages.dropdown import default_match_func
from pages.input_field import Input_v0_48_4
from pages.input_field import InputPassword_v0_48_4
from pages.settings.dialog_select_avatar import SelectUserAvatarDialog

log = logging.getLogger(__name__)

OPTION_12H_TIME = '12-hour time'
OPTION_24H_TIME = '24-hour time'


class UserSettingsPanel(BasePage):
    def __init__(self, *args, **kwargs):
        def _get_x_section(title: str) -> str:
            return self.x_root + f"//div[@class='UIUserSettingsRow' and child::div='{title}']"

        self.x_root = "//div[contains(@class, 'UIWidgetContainer') and contains(@class, 'UIUserSettings')]"
        self._x_name_section = _get_x_section('User name')
        self._x_password_section = _get_x_section('User password')
        self._x_timezone_section = _get_x_section('Time settings')
        super().__init__(*args, **kwargs)

    @property
    def _button_close(self) -> IcoButton:
        return get_div_tooltip_ico_button(page=self, ico=consts.ICO_CLOSE1)

    @property
    def user_image(self) -> WebElement:
        return self.get_desc_obj(XPathType("//div[contains(@class, 'UIUserAvatarSetting')]"))

    @property
    def _button_upload_photo(self) -> Button:
        return Button(x_root=self.x_root, driver=self._driver, label="Upload Photo", is_mui=False)

    @property
    def button_save_password(self) -> Button:
        return Button(x_root=self._x_password_section, driver=self.driver, label='Save', is_mui=False)

    @property
    def button_save_time_settings(self) -> Button:
        return Button(x_root=self._x_timezone_section, driver=self.driver, label='Save', is_mui=False)

    @property
    def button_save_name(self) -> Button:
        return Button(x_root=self._x_name_section, driver=self.driver, label='save', is_mui=False)

    @property
    def _file_input(self) -> WebElement:
        return self.get_desc_obj(XPathType('//input[@type="file"]'))

    @property
    def _button_replace_photo(self) -> Button:
        return Button(x_root=self.x_root, driver=self._driver, label="Replace Photo", is_mui=False)

    @property
    def _button_remove_photo(self) -> Button:
        return Button(x_root=self.x_root, driver=self._driver, label="Remove Photo", is_mui=False)

    @property
    def input_first_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(x_root=self.x_root, driver=self.driver, label='First Name')

    @property
    def input_last_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(x_root=self.x_root, driver=self.driver, label='Last Name')

    @property
    def input_new_password(self) -> InputPassword_v0_48_4:
        return InputPassword_v0_48_4(x_root=self.x_root, driver=self.driver, label='New Password')

    @property
    def input_old_password(self) -> InputPassword_v0_48_4:
        return InputPassword_v0_48_4(x_root=self.x_root, driver=self.driver, label='Old Password')

    @property
    def _dropdown_date_format(self) -> Select_v0_48_4:
        return Select_v0_48_4(
            label='Date Format',
            driver=self.driver,
            has_clear_button=False,
        )

    @property
    def _delete_profile_element(self) -> WebElement:
        return self.get_desc_obj("//div[@class='header' and child::div='DELETE PROFILE']/..")

    @property
    def _button_delete_profile(self) -> Button:
        return find_element(self._delete_profile_element, ".//button[text()='DELETE PROFILE']")

    @property
    def delete_profile_warning(self) -> str:
        return find_element(self._delete_profile_element, ".//div/p").text

    @property
    def date_format(self) -> StrDateType:
        return StrDateType(self._dropdown_date_format.value)

    @property
    def _dropdown_time_format(self) -> Select_v0_48_4:
        return Select_v0_48_4(
            label='Time Format',
            driver=self.driver,
            has_clear_button=False,
        )

    @property
    def time_format(self) -> str:
        return self._dropdown_time_format.value

    @property
    def timezone(self) -> str:
        return self.dropdown_timezone.value

    @property
    def dropdown_timezone(self) -> Select_v0_48_4:
        return Select_v0_48_4(
            label='Time Zone',
            driver=self._driver,
            has_clear_button=False,
        )

    def change_time_settings(
            self,
            timezone: Optional[TimeZone] = None,
            datetime_format: Optional[DateTimeFormatType] = None,
    ) -> Self:
        if timezone:
            with allure.step(f'Set time settings: {timezone=}'):
                log.info(f'Set time settings: {timezone=}')
                self.dropdown_timezone.select_option(timezone)
        if datetime_format:
            with allure.step(f'Set time settings: {datetime_format=}'):
                log.info(f'Set time settings: {datetime_format=}')
                # date
                self._dropdown_date_format.select_option(
                    date_to_str(now_pst(), fmt=datetime_format))
                # time
                _time_format = OPTION_12H_TIME if is_12h_time_format(datetime_format) else OPTION_24H_TIME
                if not default_match_func(self._dropdown_time_format.value, _time_format):
                    self._dropdown_time_format.select_option(_time_format)
        self.button_save_time_settings.click()
        self.assert_tooltip('User date time settings has been changed')
        return self

    def close(self):
        with allure.step(f'Close {self}'):
            log.info(f'Close {self}')
            self._button_close.click()
            self.wait_disappeared()

    def change_password(
            self,
            old_password: str,
            new_password: str,
            wait_spinner_disappeared: bool = True,
    ):
        with allure.step(f'Change password "{old_password}" -> "{new_password}"'):
            self.input_old_password.type_text(old_password)
            self.input_new_password.type_text(new_password)
            self.button_save_password.click()
            self.driver.client.user.current_password = new_password
            if wait_spinner_disappeared:
                self.wait_spinner_disappeared()

    def change_name(self, first_name, last_name):
        with allure.step(f'Set new user name:"{first_name}", last_name:"{last_name}"'):
            self.input_first_name.type_text(first_name, clear_with_keyboard=True)
            self.input_last_name.type_text(last_name, clear_with_keyboard=True)
            self.button_save_name.click()
            self.wait_spinner_disappeared()

    def open_upload_photo_dialog(self, path):
        with allure.step(f"{self}: upload photo: {path}"):
            log.info(f"{self}: upload photo: {path}")
            self._button_upload_photo.wait_presence()  # make sure there is a 'Upload photo' button
            self.wait_spinner_disappeared()
            self._file_input.send_keys(str(path.resolve()))  # only absolute paths
            return SelectUserAvatarDialog(driver=self._driver)

    def open_replace_photo_dialog(self, path, wait_timeout=5):
        # I have to use new parameter `wait_timeout` due to
        # problems with test `test_upload_unsupported_file`
        # (i upload invalid image, check SelectUserAvatarDialog doesn't exist then check tooltip)
        # The tooltip may already disappear till the last check ends!
        with allure.step(f"{self}: replace photo: {path}"):
            log.info(f"{self}: replace photo: {path}")
            self._button_replace_photo.wait_presence()
            self.wait_spinner_disappeared()
            self._file_input.send_keys(str(path.resolve()))  # only absolute paths
            return SelectUserAvatarDialog(driver=self._driver, check_primary_element_timeout=wait_timeout)

    def open_remove_avatar_dialog(self, delay=1):
        with allure.step(f"{self}: open 'Remove Photo' dialog"):
            log.info(f"{self}: open 'Remove Photo' dialog")
            time.sleep(delay)  # wait DOM get stable
            self._button_remove_photo.click()
            return ConfirmDialog(
                title="Delete User Avatar",
                is_mui=False,
                is_mui_confirm_button=False,
                is_mui_cancel_button=False,
                driver=self._driver,
                confirm_label="Delete",
            )

    def open_delete_profile_dialog(self) -> ConfirmDialog:
        with allure.step('Open "Delete profile" dialog'):
            log.warning(f'Open "Delete profile" dialog for {self.driver.client.user}')
            self._button_delete_profile.click()
            return ConfirmDialog(
                title='Delete Your Profile',
                is_mui=False,
                is_mui_cancel_button=False,
                is_mui_confirm_button=False,
                driver=self.driver,
            )
