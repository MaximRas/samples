from typing_extensions import override

from pages.input_field import InputFieldLegacy
from pages.base_page import BasePage
from pages.copy_value_dialog import CopyValueDialog


class CopyValueDialogLegacy(CopyValueDialog):
    @override
    @property
    def _input(self) -> InputFieldLegacy:
        if not self._input_label:
            raise RuntimeError(f'{self} has textarea, not input')
        return InputFieldLegacy(
            driver=self._driver,
            label=self._input_label,
            x_root=self.x_root,
        )


class BaseLicenseServerPage(BasePage):
    def __init__(self, title, *args, **kwargs):
        self.x_root = f"//div[contains(@class, 'MuiPaper-root') and descendant::h3='{title}']"
        super().__init__(*args, **kwargs)
