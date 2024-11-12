import logging

from pages.copy_value_dialog import CopyValueDialog

log = logging.getLogger(__name__)


class SharableLinkDialog(CopyValueDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title="Sharable link",
            confirm_label="Copy link",
            has_close_icon=False,
            is_mui=True,
            is_mui_confirm_button=True,
            has_cancel_button=False,
            *args, **kwargs,
        )
