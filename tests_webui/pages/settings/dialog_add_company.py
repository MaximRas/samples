import logging

import allure

from tools.users import generate_company_name

from pages.confirm_dialog import ConfirmDialog
from pages.dropdown import Select_v0_48_4
from pages.input_field import Input_v0_48_4
from pages.settings.dialog_add_user import AddNewUserPage

log = logging.getLogger(__name__)

TYPE_SPC = 'Service Provider Company'
TYPE_EUC = 'End User Company'
TYPE_IC = 'Integrator Company'


class AddNewCompanyDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            title='Add New Company',
            confirm_label="Add",
            check_primary_element_timeout=8,
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            **kwargs,
        )

    @property
    def company_type(self) -> Select_v0_48_4:
        return Select_v0_48_4(label="New company type", driver=self._driver, x_root=self.x_root)

    @property
    def input_company_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(x_root=self.x_root, driver=self._driver, label="Company name")

    @property
    def input_contact_email(self) -> Input_v0_48_4:
        return Input_v0_48_4(x_root=self.x_root, driver=self._driver, label="Contact E-Mail")

    @property
    def input_contact_address(self) -> Input_v0_48_4:
        return Input_v0_48_4(x_root=self.x_root, driver=self._driver, label="Contact Address")

    def fill(self, type_, name, email, address):
        '''
        FYI: all fields are compulsory: name, type, email and address since 0.46
        '''
        if name is None:
            name = generate_company_name()
        with allure.step(f'Fill form. {type_=} {name=} {email=} {address=}'):
            log.info(f'Fill form. {type_=} {name=} {email=} {address=}')
            self.company_type.select_option(type_)
            self.input_company_name.type_text(name)
            self.input_contact_email.type_text(email)
            self.input_contact_address.type_text(address)
            self.input_company_name.root.click()   # move focus from "Contact Address" to make tooltip visible
        return self

    def confirm(self, *args, **kwargs) -> AddNewUserPage:
        super().confirm(
            wait_disappeared=False,  # do not wait spinner
            delay=0,
            *args, **kwargs,
        )
        self.assert_tooltip('Company added successfully', timeout=20)
        super().wait_disappeared()
        return AddNewUserPage(driver=self._driver, cancel_label="Skip")

    def add(self, *args, **kwargs) -> AddNewUserPage:
        self.fill(*args, **kwargs)
        return self.confirm()
