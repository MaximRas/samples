import logging

import allure
from typing_extensions import Self

from pages.confirm_dialog import ConfirmDialog
from pages.input_field import Input_v0_48_4

log = logging.getLogger(__name__)


class SetValueDialog(ConfirmDialog):
    def __init__(self, input_label, *args, **kwargs):
        self._input_label = input_label
        super().__init__(*args, **kwargs)

    @property
    def input_value(self) -> Input_v0_48_4:
        return Input_v0_48_4(label=self._input_label, driver=self._driver)

    @property
    def value(self) -> str:
        return self.input_value.value

    def set_value(self, value) -> Self:
        with allure.step(f"{self}: set value: {value}"):
            log.info(f"{self}: set value: {value}")
            self.input_value.clear_with_keyboard().type_text(value)
        return self
