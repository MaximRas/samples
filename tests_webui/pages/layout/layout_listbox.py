import logging
import time
from typing import Iterable

import allure
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from tools.retry import retry
from tools import wait_objects_arrive
from tools.types import XPathType
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.webdriver import WebElement
from tools.webdriver import CustomWebDriver
from tools.webdriver import get_main_js_workaround

from pages.base_page import BasePage
from pages.dashboard import DashboardPage
from pages.confirm_dialog import ConfirmDialog
from pages.sharable_link_dialog import SharableLinkDialog
from pages.widgets.header import ICO_BUTTON_MORE
from pages.set_value_dialog import SetValueDialog

log = logging.getLogger(__name__)


class LayoutException(Exception):
    """ Base Exception """


class NoLayoutsDropoutException(LayoutException):
    pass


class NoLayoutException(LayoutException):
    pass


class LayoutNameException(LayoutException):
    pass


class LayoutPage(BasePage):
    DEFAULT_LAYOUT_NAME = 'New layout'
    x_root = XPathType("//div[contains(@class, 'grid-layout')]/../../../div[2]")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.waiter(timeout=5).until(lambda x: self.current_layout_button.text)
        except TimeoutException as exc:
            raise LayoutException('Current layout isn\'t available') from exc

    @property
    def current_layout_button(self) -> WebElement:
        return self.get_object_no_wait(XPathType(self.x_root + "//div[@role='button']"))

    @property
    def current_layout(self) -> str:
        return self.current_layout_button.get_attribute("textContent")

    @property
    def button_more(self) -> IcoButton:
        return get_ico_button(
            page=self,
            ico=ICO_BUTTON_MORE,
            x_root=self.x_root,
        )

    @property
    def button_more_add(self) -> WebElement:
        return self._find_visible_element(XPathType('//span[text()="Add"]'))

    @property
    def button_more_copy(self) -> WebElement:
        return self._find_visible_element(XPathType('//span[text()="Copy"]'))

    @property
    def button_more_rename(self) -> WebElement:
        return self._find_visible_element(XPathType('//span[text()="Rename"]'))

    @property
    def button_more_delete(self) -> WebElement:
        return self._find_visible_element(XPathType('//span[text()="Delete"]'))

    @property
    def button_more_share(self) -> WebElement:
        return self._find_visible_element(XPathType('//span[text()="Share"]'))

    @property
    def available_layouts(self) -> Iterable[str]:
        """
        Read all layouts from dropout and close dropout
        """
        self._open_layout_dropout()
        layout_names = self._layout_names
        self._close_layout_dropdown()
        return layout_names

    @property
    def _layout_names(self) -> Iterable[str]:
        layout_names = []
        for layout in self._layouts_list:
            layout_name = layout.get_attribute("textContent").strip()
            if not layout_name:
                raise LayoutNameException('Empty layout name')
            layout_names.append(layout_name)

        return layout_names

    @property
    def _layouts_list(self) -> Iterable[WebElement]:
        return self.get_objects(XPathType("//ul[@role='listbox']//li"))

    @retry(StaleElementReferenceException)
    def _select_layout_from_dropout(self, layout_name, ignore_duplicates):
        available_layouts = self._layout_names
        if not ignore_duplicates:
            if len(available_layouts) != len(set(available_layouts)):
                raise LayoutNameException(f'There are duplicates among layouts: {available_layouts}')

        if layout_name not in self._layout_names:
            raise NoLayoutException(f'Required: "{layout_name}". Available: {self._layout_names}')

        for layout_li in self._layouts_list:
            if layout_li.get_attribute("textContent") == layout_name:
                layout_li.click()
                break

        self.wait_spinner_disappeared()
        try:
            self.waiter(timeout=5).until(lambda x: self.current_layout == layout_name)
        except TimeoutException as exc:
            raise RuntimeError(
                'Layout hasn\'t been switched. Current '
                f'"{self.current_layout}", Expected: "{layout_name}"'
            ) from exc

    def _open_layout_dropout(self):
        if self._layouts_list:
            raise RuntimeError('Layouts dropout has already been opened')

        self.current_layout_button.click()
        try:
            self.waiter(timeout=5, poll_frequency=1).until(lambda x: self._layouts_list)
        except TimeoutException as exc:
            raise NoLayoutsDropoutException from exc
        time.sleep(2)  # TODO: wait layout dropout rendered (each layout has non empty text)
        return self

    def _close_layout_dropdown(self):
        self._layouts_list[0].send_keys(Keys.ESCAPE)

    def open_more_menu(self):
        time.sleep(1)
        self.button_more.click()
        # TODO: make sure menu appeared
        time.sleep(3)  # make `_find_visible_element` stable

    def open_add_dialog(self) -> SetValueDialog:
        with allure.step(f'{self}: open "add layout" dialog'):
            log.info(f'{self}: open "add layout" dialog')
            self.open_more_menu()
            self.button_more_add.click()
            return SetValueDialog(title='Add layout', driver=self._driver, input_label='Layout name')

    def open_rename_dialog(self) -> SetValueDialog:
        with allure.step(f'{self}: open "rename layout" dialog'):
            log.info(f'{self}: open "rename layout" dialog')
            self.open_more_menu()
            self.button_more_rename.click()
            return SetValueDialog(title='Rename layout', driver=self._driver, input_label='Layout name')

    def open_delete_dialog(self) -> ConfirmDialog:
        with allure.step(f'{self}: open "delete layout" dialog'):
            log.info(f'{self}: open "delete layout" dialog')
            self.open_more_menu()
            self.button_more_delete.click()
            return ConfirmDialog(driver=self._driver, title='Delete layout')

    def switch_to(self, layout_name: str, ignore_duplicates: bool = False):
        if self.current_layout == layout_name:
            log.debug(f'Do not switch layout: You are already on layout: {layout_name}')
            return self
        log.info(f'Switch layout "{self.current_layout}" -> "{layout_name}"')
        self._open_layout_dropout()
        self._select_layout_from_dropout(layout_name, ignore_duplicates=ignore_duplicates)
        return self

    def add(self, layout_name: str) -> DashboardPage:
        """
        Returns DashboardPage to have same behavior as 'share' method.
        Returned DashboardPage allows us to create widget on addded layout.
        """
        def is_correct_layout_name(driver: CustomWebDriver):
            current_layout_name: str = self.current_layout
            log.debug(f' - check layout: current="{current_layout_name}" vs expected="{layout_name}"')
            return current_layout_name == layout_name

        with allure.step(f'Create new layout: "{layout_name}"'):
            log.info(f'Create new layout: "{layout_name}"')
            self.open_add_dialog().set_value(layout_name).confirm()
            self.wait(
                is_correct_layout_name,
                RuntimeError(f'Layout has not been switched to "{layout_name}"'),
                poll_frequency=1.0,
                timeout=5,
            )
            return DashboardPage(driver=self._driver)

    def copy(self, layout_name: str, delay: int = 2) -> DashboardPage:
        """
        Returns DashboardPage to have same behavior as 'share' method.
        Returned DashboardPage allows us to create widget on copied layout.
        """
        with allure.step(f'Copy layout: "{self.current_layout}" -> "{layout_name}"'):
            log.info(f'Copy layout: "{self.current_layout}" -> "{layout_name}"')
            self.open_more_menu()
            self.button_more_copy.click()
            SetValueDialog(title='Copy layout', driver=self._driver, input_label='Layout name').\
                set_value(layout_name).confirm()
            time.sleep(delay)
            self.waiter(timeout=5).until(lambda x: self.current_layout == layout_name)
            return DashboardPage(driver=self._driver)

    def rename(self, new_name: str, delay: int = 2):
        with allure.step(f'Rename layout: "{self.current_layout}" -> "{new_name}"'):
            log.info(f'Copy layout: "{self.current_layout}" -> "{new_name}"')
            rename_layout_dialog = self.open_rename_dialog()
            rename_layout_dialog.set_value(new_name).confirm()
            time.sleep(delay)
            self.waiter(timeout=5).until(lambda x: self.current_layout == new_name)
        return self

    def delete(self, delay: int = 2):
        with allure.step(f'Delete layout: "{self.current_layout}"'):
            log.info(f'Delete layout: "{self.current_layout}"')
            self.open_delete_dialog().confirm()
            time.sleep(delay)
        return self

    def open_share_dialog(self) -> SharableLinkDialog:
        with allure.step(f'{self}: open share dialog'):
            self.open_more_menu()
            self.button_more_share.click()
            return SharableLinkDialog(driver=self._driver)

    def share(self, another_driver, delay=5, return_page=DashboardPage):
        wait_objects_arrive()
        current_layout_name = self.current_layout
        with allure.step(f'Share layout: "{current_layout_name}"'):
            log.info(f'Share layout: "{current_layout_name}"')
            share_link_dialog = self.open_share_dialog()
            link = share_link_dialog.value
            log.info(f'"{current_layout_name}" shared link: "{link}"')
            share_link_dialog.close_with_esc()

            if another_driver:
                get_main_js_workaround(another_driver, link)
                time.sleep(delay)
                return return_page(driver=another_driver)
            return None
