from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Set
from typing import Sequence
from typing import Mapping
from typing import Optional
import logging
import tempfile
import time

import allure
import requests

import consts
from tools.color import Color
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.ico_button import get_div_tooltip_ico_button
from tools.time_tools import DATETIME_FORMAT_DEFAULT
from tools.time_tools import add_seconds_to_datetime_format
from tools.time_tools import parse_datetime
from tools.types import BaseType
from tools.types import IcoType
from tools.types import IdIntType
from tools.types import LicPlateType
from tools.types import StrDateType
from tools.types import UrlType
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_elements

from pages.base_page import BasePage
from pages.base_page import NoElementException
from pages.base_page import is_element_exist
from pages.range_slider import ICO_ZOOM_IN
from pages.range_slider import ICO_ZOOM_OUT

if TYPE_CHECKING:
    from pages.object_card import ObjectCard
    from pages.object_popup_dialog import ObjectThumbnailPopup

log = logging.getLogger(__name__)

expected_meta_thumbnail = lambda attribute, card_id: {
    consts.BASE_FACE: [
        f'{card_id}',
        f'{attribute.upper()} ' + r'(\d{2}|N/A)',
        r"camera-\d+",
        PLACEHOLDER_TIME,
    ],
    consts.BASE_VEHICLE: [
        f'{card_id}',
        'N/A',
        attribute.upper(),
        r"camera-\d+",
        PLACEHOLDER_TIME,
    ],
    consts.BASE_PERSON: [
        f'{card_id}',
        r"camera-\d+",
        PLACEHOLDER_TIME,
    ],
}

PLACEHOLDER_TIME = '_PLACEHOLDER_TIME'

ICO_LICENSE_PLATE = IcoType('M175.384-200q-23.057 0-39.221-16.163Q120-232.327 120-255.384v-449.232q0-23.057 16.163-39.221Q152.327-760 175.384-760h609.232q23.057 0 39.221 16.163Q840-727.673 840-704.616v449.232q0 23.057-16.163 39.221Q807.673-200 784.616-200H175.384Zm84.693-161.692h30.461v-236.616h-25.077l-66.846 46.693L215-527.846l45.077-30.308v196.462Zm126.846 0h149.923V-392H429.385l.769-3.538q14.769-12 30.884-27.27 16.116-15.269 32.962-33.653 17.923-18.462 26.846-35.424 8.923-16.961 8.923-39.884 0-28.822-19.692-47.68-19.692-18.859-50.846-18.859-24.616 0-43.577 12.462-18.962 12.461-28.962 32.384L417-539.308q5.769-11.769 17.385-19.769 11.615-8 24.589-8 19.026 0 29.795 10.275 10.769 10.275 10.769 26.802 0 16.154-7.307 27.731-7.308 11.577-23.539 27.346Q442.615-447 425.5-431q-17.115 16-38.577 35.692v33.616Zm299.385 0q32.154 0 52.961-17.5 20.808-17.5 20.808-49.885 0-25-12.615-39.846-12.616-14.846-34.385-16.846v-1.308q19.769-3.385 29.269-15.731t9.5-33.577q0-28.461-18.807-45.192-18.808-16.731-47.731-16.731-26.491 0-42.323 13.539-15.831 13.538-26.523 27.307l26.307 14.154q7.231-11 18.5-17.5 11.27-6.5 24.039-6.5 15.769 0 26.038 9.27 10.269 9.269 10.269 24.269 0 17-12.183 25.692-12.184 8.692-31.355 8.692h-11.692v30.539h13.461q21.308 0 35.654 10 14.346 10 14.346 28.516 0 17.715-12.654 29.138-12.653 11.423-30.884 11.423-15.769 0-29-8.846-13.231-8.847-20.769-25.077L610-413.769q8.769 23.923 28.115 38 19.347 14.077 48.193 14.077ZM175.384-230.769h609.232q10.769 0 17.692-6.923t6.923-17.692v-449.232q0-10.769-6.923-17.692t-17.692-6.923H175.384q-10.769 0-17.692 6.923t-6.923 17.692v449.232q0 10.769 6.923 17.692t17.692 6.923Zm-24.615 0V-729.231-230.769Z')

ICO_OPEN_PAGE = IcoType('M429.231-316.923H283.077q-67.677 0-115.377-47.687Q120-412.298 120-479.957q0-67.658 47.7-115.389 47.7-47.731 115.377-47.731h146.154v30.769H283.077q-55.257 0-93.782 38.457-38.526 38.457-38.526 93.616 0 55.158 38.526 93.85 38.525 38.693 93.782 38.693h146.154v30.769Zm-86.539-147.692v-30.77h275.385v30.77H342.692Zm188.077 147.692v-30.769h146.154q55.257 0 93.782-38.457 38.526-38.457 38.526-93.616 0-55.158-38.526-93.85-38.525-38.693-93.782-38.693H530.769v-30.769h146.154q67.677 0 115.377 47.687Q840-547.702 840-480.043q0 67.658-47.7 115.389-47.7 47.731-115.377 47.731H530.769Z')

ICO_TOGGLE_DETECTION_AREA = IcoType('M809.231-604.615v-100.001q0-9.23-7.692-16.923-7.693-7.692-16.923-7.692H684.615V-760h100.001q23.057 0 39.221 16.163Q840-727.673 840-704.616v100.001h-30.769Zm-689.231 0v-100.001q0-23.057 16.163-39.221Q152.327-760 175.384-760h100.001v30.769H175.384q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v100.001H120ZM684.615-200v-30.769h100.001q9.23 0 16.923-7.692 7.692-7.693 7.692-16.923v-100.001H840v100.001q0 23.057-16.163 39.221Q807.673-200 784.616-200H684.615Zm-509.231 0q-23.057 0-39.221-16.163Q120-232.327 120-255.384v-100.001h30.769v100.001q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h100.001V-200H175.384Zm80-135.384v-289.232h449.232v289.232H255.384Zm30.77-30.77h387.692v-227.692H286.154v227.692Zm0 0v-227.692 227.692Z')

ICO_OBJECT_ID = IcoType('m285.154-196.923 40-159.769H180.769l8.077-30.769h143.615l47.154-185.078H235.23l7.308-30.769h144.385l39.769-159.769h28.231l-39 159.769h190.692l39-159.769h29.001l-39.77 159.769h144.385l-7.308 30.769H627.539l-46.385 185.078H724.77l-7.308 30.769H573.077l-40 159.769h-29l40-159.769H353.385l-40 159.769h-28.231Zm76.307-190.538h190.693l46.385-185.078H407.846l-46.385 185.078Z')

ICO_FACE_INFO = IcoType('M634.796-416.846q-38.424 0-63.302-25.242-24.879-25.242-24.879-62.962 0-37.719 24.697-63.143 24.698-25.423 63.122-25.423 38.425 0 63.303 25.242 24.879 25.243 24.879 62.962 0 37.72-24.698 63.143-24.697 25.423-63.122 25.423ZM425.384-206.154v-40.615q0-12.02 5.924-22.895 5.923-10.874 16.307-16.336 41.154-25.846 88.662-39.808 47.508-13.961 98.338-13.961 50.831 0 98.223 14.692 47.393 14.692 89.547 39.077 8.615 6.923 15.038 17.162 6.423 10.24 6.423 22.069v40.615H425.384Zm27.308-47.923v17.154h363.847v-17.154q-41.308-25.231-89.231-40.077Q679.385-309 634.615-309q-44.769 0-92.807 14.846-48.039 14.846-89.116 40.077Zm181.923-193.538q24.827 0 41.029-16.202t16.202-41.029q0-24.462-16.202-41.231-16.202-16.769-41.029-16.769-24.826 0-41.028 16.769-16.202 16.769-16.202 41.231 0 24.461 16.202 40.846 16.202 16.385 41.028 16.385Zm0-57.231Zm0 267.923ZM155.384-424.615v-30.77h273.693v30.77H155.384Zm0-324.616V-780h436.847v30.769H155.384Zm324.385 161.923H155.384v-30.769H500q-5.467 7.831-11.345 15.336-5.879 7.505-8.886 15.433Z')

ICO_CAMERA = IcoType('M194.615-200q-23.058 0-39.221-16.163-16.164-16.164-16.164-39.221v-449.232q0-23.057 16.164-39.221Q171.557-760 194.615-760h449.231q23.058 0 39.221 16.163 16.164 16.164 16.164 39.221v201.924L820.77-624.231v287.693L699.231-458.077v202.693q0 23.057-16.164 39.221Q666.904-200 643.846-200H194.615Zm0-30.769h449.231q10.769 0 17.692-6.923t6.923-17.692v-449.232q0-10.769-6.923-17.692t-17.692-6.923H194.615q-10.769 0-17.692 6.923T170-704.616v449.232q0 10.769 6.923 17.692t17.692 6.923Zm-24.615 0V-729.231-230.769Z')

ICO_DETECTION_TIME = IcoType('m633.154-303.923 22.692-22.692-159-160.019v-199.443h-30.769v212.692l167.077 169.462ZM480.134-120q-74.442 0-139.794-28.339-65.353-28.34-114.481-77.422-49.127-49.082-77.493-114.373Q120-405.425 120-479.866q0-74.442 28.339-139.794 28.34-65.353 77.422-114.481 49.082-49.127 114.373-77.493Q405.425-840 479.866-840q74.442 0 139.794 28.339 65.353 28.34 114.481 77.422 49.127 49.082 77.493 114.373Q840-554.575 840-480.134q0 74.442-28.339 139.794-28.34 65.353-77.422 114.481-49.082 49.127-114.373 77.493Q554.575-120 480.134-120ZM480-480Zm0 329.231q136.154 0 232.692-96.539Q809.231-343.846 809.231-480t-96.539-232.692Q616.154-809.231 480-809.231t-232.692 96.539Q150.769-616.154 150.769-480t96.539 232.692Q343.846-150.769 480-150.769Z')

ICO_GROUPED_OBJ = IcoType('M480.299-358.461q58.393 0 99.816-41.722 41.424-41.722 41.424-100.116 0-58.393-41.722-99.816-41.722-41.424-100.116-41.424-58.393 0-99.817 41.722-41.423 41.722-41.423 100.116 0 58.393 41.722 99.817 41.722 41.423 100.116 41.423Zm-.67-31.847q-45.86 0-77.591-32.101-31.73-32.102-31.73-77.962 0-45.86 32.101-77.591 32.102-31.73 77.962-31.73 45.86 0 77.591 32.101 31.73 32.102 31.73 77.962 0 45.86-32.101 77.591-32.102 31.73-77.962 31.73ZM480.11-240q-129.187 0-235.649-71.077Q138-382.154 83.077-500 138-617.846 244.35-688.923 350.703-760 479.89-760q129.187 0 235.649 71.077Q822-617.846 876.923-500 822-382.154 715.649-311.077 609.297-240 480.11-240ZM480-500Zm-.169 229.231q117.323 0 214.977-62.039Q792.462-394.846 843.923-500q-51.461-105.154-148.947-167.192-97.485-62.039-214.807-62.039-117.323 0-214.977 62.039Q167.538-605.154 115.846-500q51.692 105.154 149.178 167.192 97.485 62.039 214.807 62.039Z')

ICO_MAIN_GROUPED_OBJ = IcoType('M480.299-358.461q58.393 0 99.816-41.722 41.424-41.722 41.424-100.116 0-58.393-41.722-99.816-41.722-41.424-100.116-41.424-58.393 0-99.817 41.722-41.423 41.722-41.423 100.116 0 58.393 41.722 99.817 41.722 41.423 100.116 41.423Zm-.67-31.847q-45.86 0-77.591-32.101-31.73-32.102-31.73-77.962 0-45.86 32.101-77.591 32.102-31.73 77.962-31.73 45.86 0 77.591 32.101 31.73 32.102 31.73 77.962 0 45.86-32.101 77.591-32.102 31.73-77.962 31.73ZM480.11-240q-129.187 0-235.649-71.077Q138-382.154 83.077-500 138-617.846 244.35-688.923 350.703-760 479.89-760q129.187 0 235.649 71.077Q822-617.846 876.923-500 822-382.154 715.649-311.077 609.297-240 480.11-240Z')

ICO_VEHICLE_INFO = IcoType('M190.769-241.692v66.308q0 6.538-4.423 10.961T175.385-160h-.001q-6.538 0-10.961-4.423T160-175.384v-295.539l79.615-233.693q2.692-7.077 9.346-11.23Q255.615-720 263.385-720h436.307q7.432 0 12.757 3.981 5.326 3.98 7.936 11.403L800-470.923v295.539q0 6.538-4.423 10.961T784.616-160h-.231q-7.116 0-11.135-4.423t-4.019-10.961v-66.308H190.769ZM203-501.693h554l-65-187.538H268l-65 187.538Zm-12.231 30.77v198.462-198.462Zm99.656 141.538q17.806 0 29.844-12.469 12.039-12.469 12.039-29.789 0-18.152-12.47-30.254Q307.369-414 290.299-414q-17.904 0-30.255 12.215-12.352 12.215-12.352 30.269 0 18.055 12.464 30.093t30.269 12.038Zm380.05 0q17.677 0 29.87-12.469 12.194-12.469 12.194-29.789 0-18.152-12.306-30.254Q687.928-414 670.348-414q-17.579 0-30.002 12.215-12.423 12.215-12.423 30.269 0 18.055 12.854 30.093t29.698 12.038Zm-479.706 56.924h578.462v-198.462H190.769v198.462Z')

ICO_BAD_QUALITY_LABEL = IcoType('M480-303.308q9.769 0 16.231-6.461 6.461-6.462 6.461-15.846 0-9.385-6.461-15.847-6.462-6.461-16.231-6.461-9.769 0-15.846 6.461-6.077 6.462-6.077 15.847 0 9.384 6.077 15.846 6.077 6.461 15.846 6.461ZM464.615-415h30.77v-253h-30.77v253ZM346.923-160 160-346.561v-266.516L346.561-800h266.516L800-613.439v266.516L613.439-160H346.923Zm12.475-30.769h240.987l168.846-168.629v-240.987L600.602-769.231H359.615L190.769-600.602v240.987l168.629 168.846ZM480-480Z')

ICON_COLORS: Mapping[BaseType, Mapping[str, str]] = {
    'face': {
        'male': 'rgb(0, 178, 227)',
        'female': 'rgb(183, 48, 11)'
    },
    'vehicle': {
        'convertible': 'rgb(146, 183, 11)',
        'hatchback': 'rgb(97, 22, 2)',
        'suv': 'rgb(183, 11, 146)',
        'minivan': 'rgb(109, 133, 24)',
        'van': 'rgb(11, 60, 183)',
        'truck': 'rgb(11, 183, 134)',
        'wagon': 'rgb(203, 78, 176)',
        'sedan': 'rgb(183, 11, 60)',
        'N/A': 'rgb(97, 22, 2)'
    }
}


ICO_PATH_TO_ID: Mapping[IcoType, str] = {
    ICO_LICENSE_PLATE: "LICENSE PLATE",
    consts.ICO_CLOSE1: "CLOSE",
    ICO_OBJECT_ID: "OBJECT ID",
    ICO_DETECTION_TIME: "DATETIME",
    ICO_CAMERA: "CAMERA",
    ICO_GROUPED_OBJ: "EYE",
    ICO_MAIN_GROUPED_OBJ: "EYE",
    ICO_OPEN_PAGE: "OPEN CARD",
    ICO_TOGGLE_DETECTION_AREA: "DETECTION AREA",
    consts.ICO_SQUARE: "POPUP",
    ICO_FACE_INFO: "FACE INFO",
    ICO_VEHICLE_INFO: "VEHICLE INFO",
    ICO_BAD_QUALITY_LABEL: "BAD QUALITY OBJECT",
    ICO_ZOOM_IN: "ZOOM IN",
    ICO_ZOOM_OUT: "ZOOM OUT",
}


class InvalidEyeIconColor(Exception):
    pass


class NoEyeIconException(Exception):
    pass


class NoMetaException(Exception):
    pass


def get_tooltip_element(page: BasePage, element: WebElement) -> WebElement:
    page._action_chains.move_to_element(element).perform()
    tooltip_element = page.get_object(XPathType("//div[@data-floating-ui-portal]/div"))
    return tooltip_element


def is_element_inside(element: WebElement, container: WebElement) -> bool:
    center_x = element.rect['x'] + element.rect['width'] / 2
    center_y = element.rect['y'] + element.rect['height'] / 2
    if center_x < container.rect['x']:
        return False
    if center_y < container.rect['y']:
        return False
    if center_x > container.rect['x'] + container.rect['width']:
        return False
    if center_y > container.rect['y'] + container.rect['height']:
        return False
    return True


class ObjectThumbnail(BasePage):
    def __init__(self, x_root: XPathType, *args, **kwargs):
        self.x_root = x_root
        super().__init__(*args, **kwargs)

    def __str__(self):
        meta_text = self.meta_text
        if meta_text is None:
            return 'Thumbnail (no meta)'
        return 'Thumbnail ' + ', '.join(meta_text[:-1])

    @property
    def schema(self) -> Mapping[str, Any]:
        state = {}
        state.update(self.root.location)
        state.update(self.root.size)
        state['meta_text'] = self.meta_text
        state['icons'] = self.icons_schema
        state['cluster_size'] = self.eye_cluster_size
        state['img_url'] = self.image_url
        return state

    @property
    def detection_time(self) -> StrDateType:
        return StrDateType(self.meta_text[-1])

    @property
    def meta_elements(self) -> Sequence[WebElement]:
        elements = self.get_objects(XPathType(
            self.x_root + "//div[contains(@class, 'UIMetaData')]/div"))
        if not elements:
            raise NoMetaException
        return elements

    @property
    def meta_text(self) -> Optional[Sequence[str]]:
        meta = []
        try:
            for meta_div in self.meta_elements:
                meta.append(meta_div.text.replace('\n', ' ').strip())
        except NoMetaException:
            return None
        return meta

    @property
    def cluster_name_from_meta(self) -> Optional[str]:
        cluster_name = self.meta_text[1].split(', ')[-1]
        if cluster_name == self.meta_text:
            return None
        else:
            return cluster_name

    @property
    def _eye_nonref(self) -> IcoButton:
        return get_ico_button(self, ICO_GROUPED_OBJ, button_tag=XPathType('span'))

    @property
    def _eye_ref(self) -> IcoButton:
        return get_ico_button(self, ICO_MAIN_GROUPED_OBJ, button_tag=XPathType('span'))

    @property
    def _eye(self) -> WebElement:
        try:
            return self._eye_nonref
        except NoElementException:
            return self._eye_ref

    @property
    def eye_cluster_size(self) -> Optional[int]:
        """ Number in eye icon """
        try:
            return int(self._eye.text)
        except NoElementException:
            return None

    @property
    def icons_schema(self) -> Set[str]:
        schema = set()
        for path_element in find_elements(self.root, XPathType('.//*[name()="path"]')):
            ico = IcoType(path_element.get_attribute('d'))
            schema.add(ICO_PATH_TO_ID[ico])
        return schema

    @property
    def text(self) -> str:
        return self.root.text

    @property
    def button_popup(self) -> IcoButton:
        return get_div_tooltip_ico_button(page=self, ico=consts.ICO_SQUARE)

    @property
    def label_bad_quality(self) -> IcoButton:
        return get_ico_button(self, ICO_BAD_QUALITY_LABEL, button_tag=XPathType('span'))

    @property
    def image(self) -> WebElement:
        '''
        Image available only on objects card page.
        Thumbnail images are shown thr <a> tag class. i.e. background-image: url(...)
        '''
        return self.get_desc_obj(XPathType("//*[name()='image']"))

    @property
    def image_url(self) -> UrlType:
        return UrlType(self.image.get_attribute("xlink:href"))

    @property
    def bin_image(self) -> bytes:
        res = requests.get(self.image_url)
        res.raise_for_status()
        return res.content

    @property
    def _link_element(self) -> WebElement:
        return self.get_object_no_wait(XPathType(self.x_root + "//a"))

    @property
    def url(self) -> Optional[UrlType]:
        '''
        FYI: If thumbnail located in left part (object information) of
             appearance page it DOESN'T have url
        '''
        self.wait(
            lambda x: self._link_element is not None,
            NoElementException,
            timeout=5,
            poll_frequency=0.5,
        )
        url_ = self._link_element.get_attribute('href')
        log.info(f'{self} url: {url_}')
        return UrlType(url_)

    @property
    def id(self) -> IdIntType:
        self.wait(
            lambda x: bool(self.meta_text[0].strip()),
            RuntimeError,
            timeout=3,
            poll_frequency=0.5,
        )
        id_from_meta = int(self.meta_text[0])

        # self check
        id_from_href = int(self.url.split('/')[-1]) if self.url else None
        if id_from_href:
            if id_from_meta != id_from_href:
                raise RuntimeError

        return IdIntType(id_from_meta)

    @property
    def license_plate(self) -> LicPlateType:
        element = self.get_desc_obj(XPathType(f"//div[descendant::*[name()='path'][@d='{ICO_LICENSE_PLATE}']]/p"))
        return LicPlateType(element.text)

    def has_highlighted_border(self) -> bool:
        border_color = Color(self.root.value_of_css_property('border-color'))
        default_color = Color('rgb(229, 231, 235)')
        if border_color in (
                Color(consts.ORANGE_THEME_BUTTON_ACTIVE),
                Color(consts.BLUE_THEME_BUTTON_ACTIVE),
        ):
            return True
        if border_color == default_color:
            return False
        raise RuntimeError(f'Unknown color: {border_color}')

    def download_image(self) -> Path:
        output_file = tempfile.mktemp(suffix='.jpg')
        with open(output_file, 'wb') as f_out:
            log.debug(f'{self} -> {output_file}')
            f_out.write(self.bin_image)
        return Path(output_file)

    def open_card(self) -> ObjectCard:
        from pages.object_card import ObjectCard

        with allure.step(f"{self}: open appearance page: {self.id}"):
            log.info(f"{self}: open appearance page: {self.id}")
            time.sleep(0.2)
            self.scroll_to_element(self.root)
            self._link_element.click()
            time.sleep(2)
            self.wait_spinner_disappeared(x_root=XPathType(""))
            return ObjectCard(driver=self._driver)

    def open_popup(self) -> ObjectThumbnailPopup:
        from pages.object_popup_dialog import ObjectThumbnailPopup

        with allure.step(f"{self}: open pop-up"):
            log.info(f"{self}: open pop-up")
            self.button_popup.click()
            time.sleep(2)  # wait all elements is being rendered (especially "zoom in" and "zoom out" buttons)
            return ObjectThumbnailPopup(driver=self._driver)

    def has_eye(self) -> bool:
        try:
            return bool(self._eye)
        except NoElementException:
            return False

    def to_datetime(self) -> datetime:
        return parse_datetime(
            StrDateType(self.root.text.split("\n")[-1]),
            fmt=add_seconds_to_datetime_format(DATETIME_FORMAT_DEFAULT),
        )

    def is_head_of_cluster(self, ignore_missing_eye: bool = False) -> Optional[bool]:
        # TODO: refactoring is required
        if is_element_exist(lambda: self._eye_ref):
            return True

        if is_element_exist(lambda: self._eye_nonref):
            return False

        if ignore_missing_eye:
            log.warning(f'{self} does not have eye icon')
            return None
        raise NoEyeIconException(self)
