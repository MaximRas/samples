import logging
from datetime import datetime

import allure

from tools.types import XPathType
from tools.time_tools import parse_datetime

from pages.input_field import InputFieldLegacy
from pages.datetime_utils import DatetimeDialog


log = logging.getLogger(__name__)


class InputDate(InputFieldLegacy):
    def open_filter(self) -> DatetimeDialog:
        with allure.step(f"{self}: open dialog to choose date"):
            log.info(f"{self}: open dialog to choose date")
            self.root.click()
            return DatetimeDialog(driver=self._driver, x_root=XPathType("//div[@class='MuiPickersBasePicker-container']/.."))

    def to_datetime(self) -> datetime:
        '''
        FYI https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1394
        '''
        return parse_datetime(self.value)
