import logging
from typing import Sequence

import allure

from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.button import Button

log = logging.getLogger(__name__)


class IcoDialog(BasePage):
    def __init__(
            self,
            x_root: XPathType = XPathType("//div[@id='root']"),
            *args, **kwargs):
        self.x_root = x_root + "//div[@class='UIWidgetOverlapContent']"
        super().__init__(*args, **kwargs)

    @property
    def title(self) -> str:
        return self.get_desc_obj("//div[@class='UITitle']").text

    @property
    def subtitle(self) -> str:
        text = ''
        subtitle_elements = self.get_objects(
            self.x_root + "//div[@class='UISubTitle']",
            min_opacity=0.5,
        )
        for element in subtitle_elements:
            text += f'{element.text}\n'
        return text.strip()

    @property
    def text(self) -> str:
        ''' Title + subtitle '''
        return f'{self.title}\n{self.subtitle}'.strip()

    @property
    def ico(self) -> IcoType:
        raise NotImplementedError

    @property
    def buttons_labels(self) -> Sequence[str]:
        button_elements = self.get_objects(self.x_root + "//button")
        return [e.get_attribute('textContent') for e in button_elements]

    def get_button_by_label(self, label: str) -> WebElement:
        with allure.step(f'Look for button: {label}'):
            log.info(f'Look for button: {label}')
            return Button(
                driver=self.driver,
                label='Add location',
                is_mui=False,
                x_root=self.x_root,
            )
