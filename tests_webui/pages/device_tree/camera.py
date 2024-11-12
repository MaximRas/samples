from logging import getLogger
from typing import Iterable
from typing import Optional

from selenium.common.exceptions import NoSuchElementException
import allure

from tools.client import ApiClient
from tools.cameras import mark_camera_as_changed
from tools.cameras import get_camera_by_name
from tools.types import XPathType
from tools.types import IdStrType
from tools.webdriver import WebElement
from tools.webdriver import find_element
from tools.webdriver import find_elements

from pages.base_page import BasePage
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.device_tree import create_dialog
from pages.device_tree import get_menu_button
from pages.device_tree import get_open_menu_button

log = getLogger(__name__)


class BaseCamera:
    def __init__(self, element: WebElement, parent_page: BasePage):
        self._element = element
        self._parent_page = parent_page

    @property
    def client(self) -> ApiClient:
        return self._parent_page.driver.client

    def __str__(self) -> str:
        return self.name

    def _get_name_element(self) -> WebElement:
        return find_element(self._element, XPathType(".//span[@class='UIHighLight']"))

    @property
    def name(self) -> str:
        return self._get_name_element().text

    @property
    def highlighted_name(self) -> Optional[str]:
        try:
            element = find_element(self._get_name_element(), XPathType("./b"))
        except NoSuchElementException:
            return None
        return element.text

    @property
    def id(self) -> IdStrType:
        element = find_element(
            self._element, XPathType(".//span[contains(@class, 'UITreeCameraID')]"))
        return element.text

    def _get_tags(self) -> Iterable[WebElement]:
        elements = find_elements(self._element, XPathType(".//div[@class='UITreeCameraTags']/div"))
        return elements

    @property
    def tags(self) -> set[str]:
        return set([t.text for t in self._get_tags()])

    def is_active(self) -> bool:
        tags = self.tags
        if not ('PLUGIN ON' in tags or 'PLUGIN OFF' in tags):
            raise RuntimeError(f'{self}: there is no plugin on/off tag')
        return 'PLUGIN ON' in tags


class BaseCameraWithMenu(BaseCamera):
    @property
    def _button_open_menu(self) -> WebElement:
        return get_open_menu_button(self._element, XPathType('.//div'))

    @property
    def _button_archive(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Disable camera')

    def _open_menu(self):
        with allure.step(f'{self}: open menu'):
            log.info(f'{self}: open menu')
            mark_camera_as_changed(get_camera_by_name(self.client, self.name))
            self._button_open_menu.click()

    def open_archive_dialog(self) -> ConfirmDialog:
        self._open_menu()
        self._button_archive.click()
        return create_dialog(self, 'Disable Camera', 'Disable')

    def archive(self):
        with allure.step(f'Archive {self}'):
            log.info(f'Archive {self}')
            self.open_archive_dialog(). \
                confirm()

    def drag_and_drop(self, loc):
        with allure.step(f'Drag {self} into {loc}'):
            log.info(f'Drag {self} into {loc}')
            mark_camera_as_changed(get_camera_by_name(self.client, self.name))
            chains = self._parent_page._action_chains
            chains.drag_and_drop(self._element, loc._element).perform()
            self._parent_page.wait_spinner_disappeared()


class LeftPanelCamera(BaseCameraWithMenu):
    @property
    def _button_delete(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Delete camera')

    @property
    def _button_unarchive(self) -> Button:
        return get_menu_button(driver=self._parent_page.driver, label='Enable camera')

    def open_unarchive_dialog(self) -> ConfirmDialog:
        self._open_menu()
        self._button_unarchive.click()
        return create_dialog(self, 'Enable Camera', 'Enable')

    def open_delete_dialog(self) -> ConfirmDialog:
        with allure.step(f'Open delete dialog for {self}'):
            self._open_menu()
            self._button_delete.click()
            return create_dialog(self, 'Delete Camera', 'Submit')

    def unarchive(self):
        with allure.step(f'Unarchive {self}'):
            log.info(f'Unarchive {self}')
            self.open_unarchive_dialog(). \
                confirm()
