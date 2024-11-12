import logging
from typing import Optional

import allure
from typing_extensions import Self

from pages.confirm_dialog import ConfirmDialog
from pages.input_field import Input_v0_48_4
from pages.input_field import TextArea

log = logging.getLogger(__name__)


class _AddEditLocDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            *args, **kwargs,
        )

    @property
    def input_loc_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            driver=self.driver,
            label='Location name',
            x_root=self.x_root,
        )

    @property
    def input_loc_description(self) -> TextArea:
        return TextArea(
            x_root=self.x_root,
            label='Description',
            driver=self._driver,
        )

    def set_values(
            self,
            name: str,
            description: Optional[str] = None) -> Self:
        with allure.step(f'{self} set values: {name=} {description=}'):
            log.info(f'{self} set values: {name=} {description=}')
            self.input_loc_name.type_text(name)
            if description:
                self.input_loc_description.type_text(description)
            return self


class AddLocDialog(_AddEditLocDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(title='Add location', *args, **kwargs)


class EditLocDialog(_AddEditLocDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(title='Edit location', *args, **kwargs)
