from __future__ import annotations
import logging
from typing import Set
from typing import Sequence
from typing import TYPE_CHECKING

import allure

import consts
from tools.ico_button import get_div_tooltip_ico_button
from tools.ico_button import IcoButton
from tools.webdriver import WebElement
from tools.types import StrDateType

from pages.dialog import Dialog
from pages.range_slider import RangeSlider
from pages.object_thumbnail import ICO_LICENSE_PLATE
from pages.object_thumbnail import ICO_OPEN_PAGE
from pages.object_thumbnail import ObjectThumbnail
from pages.object_thumbnail import PLACEHOLDER_TIME

if TYPE_CHECKING:
    from pages.object_card import ObjectCard

log = logging.getLogger(__name__)

VEHICLE_TYPES = [
    "SEDAN",
    "CAB",
    "HATCHBACK",
    "MINIVAN",
    "SUV",
    "TRUCK",
    "VAN",
    "WAGON",
    "N/A",
]

expected_popup_icons = {
    consts.BASE_FACE: {'CLOSE', 'CAMERA', 'DATETIME', 'OPEN CARD', 'DETECTION AREA', 'FACE INFO', 'OBJECT ID', 'ZOOM IN', 'ZOOM OUT'},
    consts.BASE_VEHICLE: {'CLOSE', 'CAMERA', 'DATETIME', 'LICENSE PLATE', 'OPEN CARD', 'DETECTION AREA', 'VEHICLE INFO', 'OBJECT ID', 'ZOOM IN', 'ZOOM OUT'},
    consts.BASE_PERSON: {'CLOSE', 'CAMERA', 'DATETIME', 'OPEN CARD', 'DETECTION AREA', 'FACE INFO', 'OBJECT ID', 'ZOOM IN', 'ZOOM OUT'},
}

expected_popup_meta = lambda card: {
    consts.BASE_FACE: [f'{card.id}', r"(MALE|FEMALE|N\/A) (\d{2}|N\/A)", r"camera-\d+", PLACEHOLDER_TIME],
    consts.BASE_VEHICLE: [f'{card.id}', "N/A", r"|".join(VEHICLE_TYPES), r"camera-\d+", PLACEHOLDER_TIME],
    consts.BASE_PERSON: [f'{card.id}', r"camera-\d+", PLACEHOLDER_TIME],
}


class ObjectThumbnailPopup(Dialog):
    """
    We can't find `title` before pup-up dialog is created
    So we need another class for pup-up dialog
    """
    def __init__(self, *args, **kwargs):
        super().__init__(
            title=None,
            has_close_icon=True,
            custom_x_root="//div[contains(@class, 'UIDialogExtendedPhoto')]",
            *args, **kwargs,
        )

    def __str__(self):
        return f"PopUp Dialog '{self.title}'"

    @property
    def img_container(self) -> WebElement:
        ''' div element what image is docked to '''
        return self.get_desc_obj("//img/..")

    @property
    def icons_schema(self) -> Set[str]:
        header_icons = {
            'link': 'OPEN CARD',
            'fit_screen': 'DETECTION AREA',
            'close': 'CLOSE',
        }
        all_icons = ObjectThumbnail.icons_schema.__get__(self)
        for icon in self.get_objects(self.x_root + "//span[contains(@class, 'material-symbols-outlined')]"):
            all_icons.add(header_icons[icon.text])
        return all_icons

    @property
    def ico_close(self) -> IcoButton:
        return get_div_tooltip_ico_button(page=self, ico=consts.ICO_CLOSE1)

    @property
    def license_plate(self) -> WebElement:
        return self.get_object(
            self.x_root + f"//div[descendant::*[name()='path'][@d='{ICO_LICENSE_PLATE}']]/p").text

    @property
    def meta_elements(self) -> Sequence[WebElement]:
        elements = self.get_objects(self.x_root + "/div[3]/div/div")
        if len(elements) < 3:
            raise RuntimeError
        return elements

    @property
    def meta_text(self) -> Sequence[str]:
        meta = []
        for meta_div in self.meta_elements:
            meta.append(meta_div.text.replace('\n', ' ').strip())
        return meta

    @property
    def title(self) -> str:
        title_element = self.get_desc_obj("//div[contains(@class, 'UIWidgetTitle')]", min_opacity=0.75)
        return title_element.text

    @property
    def button_open_card(self) -> IcoButton:
        return get_div_tooltip_ico_button(page=self, ico=ICO_OPEN_PAGE)

    @property
    def detection_time(self) -> StrDateType:
        return ObjectThumbnail.detection_time.__get__(self)

    def zoom_in(self) -> None:
        self._zoom_control.zoom_in()

    def zoom_out(self) -> None:
        self._zoom_control.zoom_out()

    def reset_scale(self) -> None:
        self._zoom_control.zoom_out()

    @property
    def _zoom_control(self) -> RangeSlider:
        return RangeSlider(driver=self._driver, x_root=self.x_root)

    def open_card(self) -> ObjectCard:
        from pages.object_card import ObjectCard

        with allure.step(f'{self}: open card'):
            log.info(f'{self}: open card')
            self.button_open_card.click()
            return ObjectCard(driver=self._driver)
