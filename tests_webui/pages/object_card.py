import logging
import re
import time

from typing import Any
from typing import Optional

import allure
from typing_extensions import Self

import consts
from pages.confirm_dialog import ConfirmDialog
from tools.getlist import GetList
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_element

from pages.base_page import BasePage
from pages.base_page import PageDidNotLoaded
from pages.ico_dialog import IcoDialog
from pages.button import Button
from pages.grid_items import GridItemsPage
from pages.input_field import ClusterNameInput
from pages.input_field import TextArea
from pages.object_thumbnail import ObjectThumbnail
from pages.object_thumbnail import PLACEHOLDER_TIME
from pages.search.results_v2 import SearchResultPageV2

log = logging.getLogger(__name__)

# second meta for vehicle in appearance page should be recognized license plate 'scs1061'
# now it is N/A because of
# https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/243
expected_meta_card = lambda attribute, card_id: {
    consts.BASE_FACE: [f'{card_id}', f'{attribute.upper()} ' + r'(\d{2}|N/A)', r"camera-\d+", PLACEHOLDER_TIME],
    consts.BASE_VEHICLE: [f'{card_id}', 'N/A', attribute.upper(), r"camera-\d+", PLACEHOLDER_TIME],
    consts.BASE_PERSON: [f'{card_id}', r"camera-\d+", PLACEHOLDER_TIME],
}

expected_icons_card_no_cluster = {
    consts.BASE_FACE: {'CAMERA', 'DATETIME', 'POPUP', 'OBJECT ID', 'FACE INFO'},
    consts.BASE_VEHICLE: {'CAMERA', 'LICENSE PLATE', 'DATETIME', 'POPUP', 'OBJECT ID', 'VEHICLE INFO'},
    consts.BASE_PERSON: {'CAMERA', 'DATETIME', 'POPUP', 'OBJECT ID'},  # 'FACE INFO' has been deleted due to https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1195
}
expected_icons_card_cluster = {base: icons.union({'EYE'}) for base, icons in expected_icons_card_no_cluster.items()}


class SubToggle(BasePage):
    def __init__(self, x_root: XPathType, *args, **kwargs):
        self.x_root = XPathType(x_root + "//div[child::div[contains(text(), 'subscription')] and child::button[@role='switch']]")
        super().__init__(*args, **kwargs)


class CardMainThumbnail(ObjectThumbnail):
    pass


class ObjectCard(BasePage):
    x_root = XPathType("//div[contains(@class, 'UILayoutContent') and descendant::div[contains(text(), 'Similar objects')]]")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def thumbnail(self) -> CardMainThumbnail:
        """ Thumbnail in the left upper corner """
        return ObjectThumbnail(
            XPathType(self.x_root + "//div[@class='UIWidgetBody' and child::div='Object properties']/div[1]"),
            driver=self._driver,
        )

    @property
    def sub_toggle(self) -> SubToggle:
        return SubToggle(driver=self._driver, x_root=self.x_root)

    @property
    def button_back(self) -> WebElement:
        # FYI: this button is out of root container
        return self.get_object(XPathType(f"//button[descendant::*[@d='{consts.ICO_LEFT_ARROW}']]"))

    @property
    def input_name(self) -> ClusterNameInput:
        return ClusterNameInput(x_root=self.x_root, driver=self._driver)

    @property
    def name(self) -> str:
        return self.input_name.value

    @property
    def _input_notes(self) -> TextArea:
        return TextArea(
            x_root=self.x_root,
            label="Object's details",
            driver=self._driver,
        )

    @property
    def notes(self) -> str:
        return self._input_notes.input.get_attribute("textContent")

    @property
    def id(self) -> int:
        id_from_thumbnail = self.thumbnail.id
        id_from_url = int(self.url.split('/')[-1])
        if id_from_url != id_from_thumbnail:
            raise RuntimeError
        return id_from_thumbnail

    @property
    def button_save_changes(self) -> Button:
        return Button('Submit', driver=self._driver, is_mui=False)

    @property
    def similar_objects_grid(self) -> GridItemsPage:
        return GridItemsPage(
            x_root=XPathType(self.x_root + "/div[2]"),
            driver=self._driver,
        )

    @property
    def similar_objects(self) -> GetList[ObjectThumbnail]:
        try:
            return self.similar_objects_grid.thumbs
        except PageDidNotLoaded:
            log.warn('There is no "similar objects" area')
            return []

    @property
    def similar_objects_count(self) -> Optional[int]:
        '''
        FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1692870515423259
        '''
        counter_element = find_element(self.similar_objects_grid.root, ".//div[@class='UIWidgetTitle']")
        try:
            counter = re.findall(r" \((\d+)\)$", counter_element.text)[0]
        except IndexError:
            return None
        return int(counter)

    @property
    def message(self) -> str:
        return IcoDialog(
            driver=self.driver,
            x_root=self.similar_objects_grid.x_root,
        ).text

    @property
    def change_cluster_name_popup(self) -> ConfirmDialog:
        return ConfirmDialog(title='Change cluster name',
                             driver=self._driver,
                             is_mui=False,
                             is_mui_confirm_button=False,
                             is_mui_cancel_button=False,
                             has_section_message=False)

    def back(
            self,
            page_class: Optional[Any] = None,
            return_page: bool = True,
    ) -> Optional[BasePage]:
        with allure.step('Click "Back" button'):
            self.button_back.click()
            if not return_page:
                return
            if page_class:
                return page_class(driver=self._driver)
            return SearchResultPageV2(driver=self._driver)

    def set_name(
            self,
            name: str,
            clear_with_keyboard: bool = True,
            *args, **kwargs) -> Self:
        with allure.step(f"{self}: set objects name: {name}"):
            log.info(f"{self}: set objects name: {name}")
            self.input_name.type_text(name, clear_with_keyboard=clear_with_keyboard, *args, **kwargs)
            time.sleep(1)
            return self

    def select_name(self, option: str) -> Self:
        with allure.step(f'Select object name: {option}'):
            log.info(f'{self}: select object name: {option}')
            self.input_name.select_option(option)
            return self

    def set_notes(self, notes: str) -> Self:
        with allure.step(f"{self}: set objects notes: {notes}"):
            log.info(f"{self}: set objects notes: {notes}")
            self._input_notes.type_text(notes, clear_with_keyboard=True)
            time.sleep(1)
            return self

    def save_changes(self) -> None:
        with allure.step(f"{self}: save changes"):
            log.info(f"{self}: save changes")
            self.button_save_changes.click()
            self.wait_spinner_disappeared(timeout_appeared=2)
            self.assert_tooltip('Saved', timeout=10)
