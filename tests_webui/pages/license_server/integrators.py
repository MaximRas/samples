import logging

import allure

from pages.button import Button
from pages.input_field import InputFieldLegacy
from pages.confirm_dialog import ConfirmDialog
from pages.license_server import BaseLicenseServerPage

log = logging.getLogger(__name__)


class AddNewIntegratorDialog(ConfirmDialog):
    # TODO: add more fields (first name, last name, email, password)
    @property
    def input_company_name(self) -> InputFieldLegacy:
        return InputFieldLegacy(
            x_root=self.x_root,
            driver=self._driver,
            label="Company name",
        )


class IntegratorsPage(BaseLicenseServerPage):
    def __init__(self, *args, **kwargs):
        super().__init__(title='Integrators List', *args, **kwargs)

    @property
    def button_generate_license(self):
        return Button(label='Add New Integrator', x_root=self.x_root, driver=self._driver)

    def open_add_new_integrator_dialog(self):
        with allure.step(f'{self}: open dialog "Add New Integrator"'):
            log.info(f'{self}: open dialog "Add New Integrator"')
            self.button_generate_license.click()
            return AddNewIntegratorDialog(
                title='Add New Integrator',
                confirm_label='Add New Integrator',
                driver=self._driver,
            )
