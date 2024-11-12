import logging

import allure

from pages.confirm_dialog import ConfirmDialog
from pages.input_field import Input_v0_48_4

log = logging.getLogger(__name__)


class CopyValueDialog(ConfirmDialog):
    '''
    root element sometimes contains attribute '@role="dialog" (sometimes it doesn't though)
    if dialog is modal (modal means it is possible to close dialog by clicking outside of its borders)
    So don't rely on @role attribute.
    Example of non-modal dialog: shared link

    Headless chrome doesn't support clipboard so we have to copy value by reading it from DOM.
    Don't click "Copy" button since it leads to error: "NotAllowedError: Write permission denied."
    (it annoys people with sentry errors: https://metapix.sentry.io/issues/4461479810/events/?project=4505787239038976&referrer=previous-event)
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/558

    Possible workaround: https://www.appsloveworld.com/bestanswer/selenium/138/how-to-fetch-copied-content-from-a-clipboard-selenium-headless-mode
    '''
    def __init__(
            self,
            confirm_label='Copy',
            cancel_label='Close',
            input_label=None,
            has_cancel_button=True,
            *args, **kwargs,
    ):
        self._input_label = input_label
        self._has_cancel_button = has_cancel_button
        super().__init__(
            check_primary_element_timeout=10,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            is_mui=kwargs.pop('is_mui', False),
            is_mui_confirm_button=kwargs.pop('is_mui_confirm_button', False),
            is_mui_cancel_button=False,
            *args, **kwargs,
        )

    @property
    def button_cancel(self):
        if self._has_cancel_button:
            return super().button_cancel
        else:
            raise RuntimeError(f'{self} does not have "cancel" button')

    @property
    def message(self):
        element = self.get_desc_obj("//div[contains(@class, 'UISectionMessage')]")
        return element.text

    @property
    def _input(self) -> Input_v0_48_4:
        if not self._input_label:
            raise RuntimeError(f'{self} has textarea, not input')
        return Input_v0_48_4(
            driver=self._driver,
            label=self._input_label,
            x_root=self.x_root,
        )

    @property
    def value(self):
        with allure.step(f"{self} getting value"):
            log.info(f"{self} getting value")
            if self._input_label:
                return self._input.value
            else:
                textarea = self.get_desc_obj("//textarea[not(@aria-hidden)]")
                return textarea.text

    def copy(self, *args, **kwargs):
        with allure.step(f"{self}: copy value into buffer"):
            super().confirm(
                kwargs.pop('wait_spinner_disappeared', False),
                kwargs.pop('delay', 1),
                *args,
                **kwargs,
            )
