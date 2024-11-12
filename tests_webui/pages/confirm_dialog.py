''' Base class for confirmation dialogs '''

import logging
import time

import allure

from pages.dialog import Dialog
from pages.button import Button

log = logging.getLogger(__name__)


class ConfirmDialog(Dialog):
    def __init__(
            self,
            confirm_label: str = "Submit",   # FYI https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1709670603110429
            cancel_label: str = "Cancel",
            *args, **kwargs,
    ):
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._is_mui_confirm_button = kwargs.pop('is_mui_confirm_button', True)
        self._is_mui_cancel_button = kwargs.pop('is_mui_cancel_button', True)
        super().__init__(*args, **kwargs)
        time.sleep(2)   # sometimes confirmation dialog disappears too fast

        # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1140
        # TODO: look for other dialogs which require such check
        # TODO: use relateive measure of length?
        assert self.root.size['width'] > 300 and self.root.size['height'] > 100

    @property
    def button_cancel(self) -> Button:
        return Button(
            x_root=self.x_root,
            label=self._cancel_label,
            driver=self._driver,
            is_mui=self._is_mui_cancel_button,
        )

    @property
    def button_confirm(self) -> Button:
        return Button(
            x_root=self.x_root,
            label=self._confirm_label,
            driver=self._driver,
            is_mui=self._is_mui_confirm_button,
        )

    def cancel(self, delay=5) -> None:
        with allure.step(f"{self}: cancel"):
            log.info(f"{self}: cancel")
            self.button_cancel.click()
            self.wait_disappeared(timeout=3)
            time.sleep(delay)

    def confirm(self, delay=3, wait_disappeared=True) -> None:
        with allure.step(f"{self}: confirm"):
            log.info(f"{self}: confirm")
            self.button_confirm.click()
            if wait_disappeared:
                self.wait_spinner_disappeared()
                self.wait_disappeared()
                time.sleep(delay)
            else:
                log.info(' - do not wait dialog disappeared')
