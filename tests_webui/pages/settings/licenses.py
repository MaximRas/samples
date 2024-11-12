import logging
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Sequence

import allure

from tools.license_server import LicenseServerLicenseData
from tools.types import IdStrType
from tools.types import StrDateType
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import NoElementException
from pages.button import Button
from pages.navigation import BaseContentTable
from pages.navigation import get_column
from pages.set_value_dialog import SetValueDialog

log = logging.getLogger(__name__)


class UILicenseRow:
    def __init__(self, element: WebElement):
        self._element = element

    def __str__(self):
        return f"License {self.key}"

    # @property
    # def type(self):
    #     raise NotImplementedError  # TODO: type hinting
    #     return get_column(self._element, 0).text

    @property
    def key(self) -> IdStrType:
        text = get_column(self._element, 1).text
        return IdStrType(text)

    @property
    def activated_at(self) -> StrDateType:
        return StrDateType(get_column(self._element, 2).text)

    @property
    def expires_at(self) -> StrDateType:
        return StrDateType(get_column(self._element, 3).text)

    @property
    def days(self) -> int:
        return int(get_column(self._element, 4).text)

    @property
    def cameras(self) -> int:
        return int(get_column(self._element, 5).text)


class LicensesPage(BaseContentTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title='Licenses', **kwargs)

    @property
    def button_activate_demo_license(self) -> Button:
        return Button('Activate demo license', x_root=self.x_root, driver=self._driver, is_mui=False)

    @property
    def button_activate_new_license(self) -> Button:
        return Button('Activate new license', x_root=self.x_root, driver=self._driver, is_mui=False)

    @property
    def licenses(self) -> Iterable[UILicenseRow]:
        return [UILicenseRow(row) for row in self._rows]

    @property
    def schema(self) -> Sequence[Mapping]:
        licenses_ = []
        for lic in self.licenses:
            licenses_.append(
                {
                    "key": lic.key,
                    # "expires_at": lic.expires_at,
                    # "activated_at": lic.activated_at,
                    "days": lic.days,
                    "cameras": lic.cameras,
                }
            )
        return licenses_

    @property
    def _licenses_summary_element(self) -> WebElement:
        return self.get_desc_obj(XPathType("//div[contains(@class, 'UISectionMessage')]"))

    @property
    def licenses_summary(self) -> Optional[str]:
        try:
            return self._licenses_summary_element.text
        except NoElementException:
            return None

    def activate_demo_license(self) -> None:
        with allure.step(f"{self}: activate demo license"):
            log.info(f"{self}: activate demo license")
            self.button_activate_demo_license.click()  # TODO: `button_activate_demo_license` disapeared????
            self.assert_tooltip('Demo license has been activated')

    def open_activate_new_license_dialog(self) -> SetValueDialog:
        with allure.step(f"{self}: open 'Activate New License' dialog"):
            log.info(f"{self}: open 'Activate New License' dialog")
            self.button_activate_new_license.click()
            self.wait_spinner_disappeared()
            return SetValueDialog(
                title='Activate new license',
                driver=self._driver,
                input_label='License Key',
                is_mui=False,
                is_mui_confirm_button=False,
                is_mui_cancel_button=False,
            )

    def activate_license(self, lic: LicenseServerLicenseData) -> None:
        with allure.step(f'Activate {lic}'):
            log.info(f'Activate {lic}')
            activation_dialog = self.open_activate_new_license_dialog()
            activation_dialog.set_value(lic.key)
            activation_dialog.confirm(wait_disappeared=False)
            self.assert_tooltip('License has been activated')
            self.wait_spinner_disappeared()
