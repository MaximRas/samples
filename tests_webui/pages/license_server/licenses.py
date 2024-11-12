import logging
from typing import Sequence
from typing import Mapping

import allure
from typing_extensions import Self

from pages import BaseTableRow
from tools import WebElement
from tools.types import EmailType

from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.input_field import InputFieldLegacy
from pages.license_server import BaseLicenseServerPage
from pages.license_server import CopyValueDialogLegacy
from pages.license_server.table import LicenseServerBaseContentTable
from pages.navigation import get_column


log = logging.getLogger(__name__)


class LicensesPage(BaseLicenseServerPage):
    def __init__(self, *args, **kwargs):
        super().__init__(title='Licenses List', *args, **kwargs)

    @property
    def button_generate_license(self):
        return Button(label="Generate New License", x_root=self.x_root, driver=self._driver)

    @property
    def license_table(self):
        return LicenseList(x_root=self.x_root, driver=self._driver)

    def _open_generate_license_dialog(self):
        with allure.step(f"{self}: open 'generate new license dialog'"):
            log.info(f"{self}: open 'generate new license dialog'")
            self.button_generate_license.click()
            return GenerateLicensePopup(
                title="Generate New License",
                confirm_label="Generate",
                driver=self._driver,
            )

    def generate_license(self, days, channels, contract_id=""):
        with allure.step(f'{self}: generate license: {days=} {channels=} {contract_id}'):
            log.info(f'{self}: generate license: {days=} {channels=} {contract_id}')
            dialog = self._open_generate_license_dialog()
            dialog.set_day(days)
            dialog.set_channels(channels)
            if contract_id:
                dialog.set_contract_id(contract_id)
            dialog.confirm()

            copy_license_dialog = CopyValueDialogLegacy(
                driver=self._driver,
                title='Please Copy the License Keys',
                is_mui=True,
                has_close_icon=False,
                input_label='License Key',
                has_cancel_button=False,
            )
            license_key = copy_license_dialog.value
            copy_license_dialog.close_with_esc()
            return license_key


class LicenseList(LicenseServerBaseContentTable):
    @property
    def licenses(self):
        return [LicenseInfo(row, self) for row in self._rows]

    @property
    def schema(self) -> Sequence[Mapping]:
        schema_ = []
        for key in self.licenses:
            schema_.append(
                {
                    "key": key.key,
                    "type": key.key_type,
                    "channels": key.channels,
                    "contract": key.contract,
                    "days": key.days,
                    "company": key.company_name,
                    "email": key.account_manager,
                    "status": key.status,
                    "expiration_date": key.expiration_date,
                    "days_left": key.days_left,
                    "activation_date": key.activation_date,
                }
            )
        return schema_

    def find_license_by_key(self, license_key):
        log.info(f'{self}: find license by key: {license_key}')
        for row in self.schema:
            if row.key == license_key:
                return row
        return 'License not found'


class GenerateLicensePopup(ConfirmDialog):
    @property
    def days_field(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label='Days',
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def channels_field(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label='Channels',
            driver=self._driver,
            x_root=self.x_root,
        )

    @property
    def _input_contract_id(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            label='Contract',
            driver=self._driver,
            x_root=self.x_root,
        )

    def set_contract_id(self, contract_id: str) -> Self:
        self._input_contract_id.type_text(contract_id)
        return self

    def set_day(self, days):
        log.info(f'{self}: set days: {days}')
        self.days_field.type_text(str(days))
        return self

    def set_channels(self, channels):
        log.info(f'{self}: set channels: {channels}')
        self.channels_field.type_text(str(channels))
        return self


class LicenseInfo(BaseTableRow):
    def __str__(self):
        return f"LicenseInfo {self.key}"

    @property
    def key(self):
        return self.get_field_by_header('Key')

    @property
    def key_type(self):
        return self.get_field_by_header('Type')

    @property
    def channels(self):
        return self.get_field_by_header('Channels')

    @property
    def days(self):
        return self.get_field_by_header('Days')

    @property
    def company_name(self) -> str:
        return self.get_field_by_header('Company')

    @property
    def contract(self) -> str:
        return self.get_field_by_header('Contract')

    @property
    def account_manager(self) -> str:
        return self.get_field_by_header('Account Manager')

    @property
    def status(self) -> str:
        return self.get_field_by_header('Status')

    @property
    def expiration_date(self) -> str:
        return self.get_field_by_header('Expiration Date')

    @property
    def activation_date(self) -> str:
        return self.get_field_by_header('Activation Date')

    @property
    def days_left(self) -> str:
        return self.get_field_by_header('Days Left')

    @property
    def button_action(self) -> WebElement:
        return get_column(self._element, 10, xpath=".//button")
