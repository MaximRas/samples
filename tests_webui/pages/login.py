from typing import Optional
import logging
import time

import allure

from tools.types import EmailType
from tools import config
from tools.types import XPathType
from tools.types import CompanyNameType
from tools.client import ApiClient
from tools.users import auth_client
from tools.users import get_available_companies
from tools.users import get_user
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.base_page import PageDidNotLoaded
from pages.button import Button
from pages.button import NoButtonException
from pages.dw_login import DWLoginPage
from pages.input_field import Input_v0_48_4
from pages.input_field import InputPassword_v0_48_4
from pages.root import RootPage
from pages.reset_password import SendCodeDialog

log = logging.getLogger(__name__)


class LoginException(Exception):
    pass


class SwitchSystemDialogIsNotAvailable(Exception):
    ''' FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1466 '''


class LoginPage(BasePage):
    path = '/log-in'
    x_root = XPathType("//div[@class='UIBasicDialog' and descendant::button='Log in with EMail']")

    @property
    def email(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            x_root=self.x_root,
            label='E-Mail',
            driver=self._driver,
        )

    @property
    def password(self) -> InputPassword_v0_48_4:
        return InputPassword_v0_48_4(
            x_root=self.x_root,
            label='Password',
            driver=self._driver,
        )

    @property
    def button_dw_cloud(self) -> Button:
        return Button(x_root=self.x_root, label='With', driver=self._driver, is_mui=False)

    @property
    def button_nx_cloud(self) -> Button:
        '''
        FYI: html code of button looks like
        <button class="UIButton xs contained" type="button">
          "With"
          "NX Cloud"
        </button>

        As you can see the title comprise of 2 string lines
        And looks like It is possible to find this element with the first line.
        '''
        return Button(x_root=self.x_root, label='With', driver=self._driver, is_mui=False)

    @property
    def button_login(self) -> Button:
        return Button(
            x_root=self.x_root,
            label='Log in with EMail',
            driver=self._driver,
            is_mui=False,
        )

    @property
    def _link_reset_password(self) -> WebElement:
        return self.get_object(self.x_root + XPathType("//a[text()='Reset Password']"))

    def authorize_via_dwnx(self) -> RootPage:
        """
        NB: This method is workaround.
        Problem is in staging environment:
        Theme is being changed time by time and we don't know which theme is on staging.

        Solution is: try to auth via DW cloud. Auth via NX cloud if previous try has failed.
        """
        try:
            return self.authorize_via_dw()
        except NoButtonException as exc:
            log.info(f"Exception has been caught: {exc}. Seems like there is no button 'DW Cloud'")
        return self.authorize_via_nx()

    def authorize_via_dw(self) -> RootPage:
        with allure.step(f"{self}: authorize with DW Cloud"):
            log.info(f"{self}: authorize with DW Cloud")
            self.button_dw_cloud.click()
            dw_login_page = DWLoginPage(
                driver=self._driver,
                check_primary_element_timeout=10,
            )
            return dw_login_page.login(
                email=EmailType(config.user_config["DWNX"]["email"]),
                password=config.user_config["DWNX"]["password"],
            )

    def authorize_via_nx(self) -> RootPage:
        with allure.step(f"{self}: authorize with NX Cloud"):
            log.info(f"{self}: authorize with NX Cloud")
            self.button_nx_cloud.click()
            dw_login_page = DWLoginPage(
                driver=self._driver,
                check_primary_element_timeout=10,
            )
            return dw_login_page.login(
                email=EmailType(config.user_config["DWNX"]["email"]),
                password=config.user_config["DWNX"]["password"],
            )

    def submit_data(
            self,
            email: EmailType,
            password: str,
            wait_disappeared: bool = True,
    ) -> None:
        '''
        You may need call `wait_spinner_disappeared` after using this method
        '''
        with allure.step(f'Fill form with {email=} {password=}'):
            self.email.type_text(email)
            self.password.type_text(password)
            self.button_login.click()
            if wait_disappeared:
                self.wait_disappeared(timeout=20)

    def reset_code(self) -> SendCodeDialog:
        '''
        Rese
        '''
        with allure.step('Reset code: Open "Send code" dialog'):
            log.info('Reset code: Open "Send code" dialog')
            self._link_reset_password.click()
            return SendCodeDialog(driver=self.driver)

    def _choose_company(
            self,
            email: EmailType,
            company_name: CompanyNameType,
            ignore_choosing_company: bool,
            use_search: bool,
            choose_default_company: bool) -> None:
        from pages.switch_company import SwitchSystemDialog

        available_companies = get_available_companies(self.driver.client)
        if ignore_choosing_company:
            if len(available_companies) <= 1:
                raise RuntimeError(f'Unexpected behavior: {ignore_choosing_company=} but there are no other companies')

        if len(available_companies) == 1:
            self.driver.client.set_company(available_companies[0])

        if len(available_companies) > 1 and not ignore_choosing_company:
            try:
                select_system_dialog = SwitchSystemDialog(driver=self._driver)
            except PageDidNotLoaded as exc:
                raise SwitchSystemDialogIsNotAvailable from exc

            if company_name:
                if use_search:
                    select_system_dialog.search(company_name)
                select_system_dialog.select_by_name(company_name)
            elif choose_default_company:
                select_system_dialog.select_by_index(0)
            else:
                raise LoginException(f"Unexpected behavior: {email} has several companies")
            select_system_dialog.wait_disappeared()

    def login(
            self,
            email: Optional[EmailType] = None,
            password: str = config.user_config['_default_pwd'],
            company_name: Optional[CompanyNameType] = None,
            choose_default_company: bool = True,
            ignore_choosing_company: bool = False,
            use_search: bool = False,
            return_page=RootPage) -> RootPage:
        '''
        `ignore_choosing_company` is required for sharing: we pass company id with url of shared widget/layout
          so that we don't neet to choose company after opening shared widget/layout any more
        '''
        # assert company or choose_default_company or ignore_choosing_company
        if not email:
            email = self.driver.client.user.email
            log.info(f'{self}: use email by default: {email}')
        elif email != self.driver.client.user.email:
            log.warning(f'{self}: setting another user for ApiClient')
            # NB: workaround to get user id
            user_id = auth_client(   # type: ignore (Could not access item in TypedDict)
                ApiClient(),
                email=email,
                password=password,
            )['user_id']
            self.driver.client.set_user(
                get_user(self.driver.client, user_id)
            )

        if not company_name:
            company_name = self.driver.client.company.name
            log.info(f'{self}: use company by default: {company_name}')

        with allure.step(f"login as email:{email} password:{password} company:{company_name}"):
            log.info(f"login as email:{email} password:{password} company:{company_name}")
            self.submit_data(email, password)
            self._choose_company(
                email=email,
                company_name=company_name,
                use_search=use_search,
                ignore_choosing_company=ignore_choosing_company,
                choose_default_company=choose_default_company,
            )
            if return_page:
                self.wait_spinner_disappeared()
                page_to_return = return_page(driver=self._driver)
                time.sleep(3)  # prevent ElementClickInterceptedException during cliking buttons in left menu
                return page_to_return
