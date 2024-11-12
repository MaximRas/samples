import logging

from pages.confirm_dialog import ConfirmDialog

log = logging.getLogger(__name__)

# TODO: "Reselect File" button


class SelectUserAvatarDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            has_close_icon=True,
            confirm_label='Upload',
            title='Crop User Avatar',
            is_mui=False,
            is_mui_confirm_button=False,
            *args, **kwargs,
        )

    @property
    def button_reselect_file(self):
        raise NotImplementedError

    @property
    def button_cancel(self):
        raise NotImplementedError

    @property
    def cropper(self):
        return self.get_desc_obj('//div[@class="advanced-cropper__background-wrapper"]/div')

    def cancel(self, *args, **kwargs):
        raise NotImplementedError
