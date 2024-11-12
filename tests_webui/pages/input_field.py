import logging
import time
from typing import Optional

from typing_extensions import Self
from typing_extensions import override

import consts
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import IcoType
from tools.types import XPathType

from pages.checkbox import CheckboxLegacy
from pages.dropdown import BaseDropdown
from pages.input_base import BaseInput
from pages.input_base import BaseInputPassword
from pages.input_base import BaseLegacyInputField
from pages.input_base import InputTemplateLegacy
from pages.input_base import InputTemplate_v0_48_4

log = logging.getLogger(__name__)


MODE_ONLY_FILLED = "Only Filled"
MODE_SPECIFIC_NAME = "Specific Name"


class InputFieldLegacy(BaseLegacyInputField, InputTemplateLegacy):
    pass


class InputWithCheckboxLegacy(InputFieldLegacy):
    @property
    def checkbox(self) -> CheckboxLegacy:
        return CheckboxLegacy(
            xpath=self.x_root + "//button",
            driver=self._driver,
            name=self._label,
        )


class OnlyFilledInput(InputFieldLegacy, BaseDropdown):
    '''
    Input for such inputs as: "Cluster's name",  "Object's details", "Vehicle license plate"
    '''
    def __init__(self, *args, **kwargs):
        InputFieldLegacy.__init__(self, *args, **kwargs)
        BaseDropdown.__init__(self, multiselect_mode=False, *args, **kwargs)
        self.default_value = ''

    @property
    def button_modes(self) -> IcoButton:
        return get_ico_button(self, IcoType('M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z'))

    def expand(self, *args, **kwargs) -> Self:
        self._expand(lambda: self.button_modes.click(), *args, **kwargs)
        return self

    def _select_mode(self, mode: str) -> None:
        assert mode in (MODE_ONLY_FILLED, MODE_SPECIFIC_NAME)
        self.select_option(mode)

    def select_only_filled_mode(self) -> None:
        self._select_mode(MODE_ONLY_FILLED)
        assert self.value.lower() == MODE_ONLY_FILLED.lower()

    def select_specific_name_mode(self) -> None:
        self._select_mode(MODE_SPECIFIC_NAME)
        assert self.value == ""


class InputWithSelect(InputFieldLegacy, BaseDropdown):
    def __init__(self, *args, **kwargs):
        InputFieldLegacy.__init__(self, *args, **kwargs)
        BaseDropdown.__init__(self, multiselect_mode=False, *args, **kwargs)

    @property
    def button_expand(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_EXPAND_MENU)

    @property
    def button_collapse(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_COLLAPSE_BUTTON)

    def type_text(self, *args, **kwargs) -> None:
        collapse = kwargs.pop('collapse', True)
        super().type_text(*args, **kwargs)
        time.sleep(1)
        if collapse and self.options:
            self.collapse()


class ClusterNameInput(InputWithSelect):
    X_DROPDOWN_LIST = XPathType("//div[@class='UITooltipOld']")
    X_DROPDOWN_OPTION = XPathType("/div/div")

    def __init__(self, *args, **kwargs):
        super().__init__(label="Cluster's name", *args, **kwargs)

    def expand(self, *args, **kwargs) -> Self:
        time.sleep(1)
        self._expand(lambda: self.root.click(), *args, **kwargs)
        return self


class InputPassword(BaseInputPassword, InputTemplateLegacy):
    pass


class CameraPickerInput(BaseInput, InputTemplateLegacy):
    @override
    @property
    def value(self) -> str:
        return self.text


class Base_v0_48_4_InputField(BaseLegacyInputField):
    @property
    def tooltip(self) -> Optional[str]:
        element = self.get_object_or_none_no_wait(self.x_root + "/..//div[contains(@class, 'text-red')]")
        return element.text if element else None


class Input_v0_48_4(Base_v0_48_4_InputField, InputTemplate_v0_48_4):
    pass


class InputPassword_v0_48_4(BaseInputPassword, InputTemplate_v0_48_4):
    pass


class SearchInput(InputFieldLegacy):
    def __init__(self, *args, **kwargs):
        # since 0.45 search fields of device three have clear button
        super().__init__(has_clear_button=True, *args, **kwargs)


class TextArea(InputFieldLegacy):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            input_tag=XPathType('textarea[not(@aria-hidden)]'),
            **kwargs,
        )
