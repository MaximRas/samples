''' This dialog appears if you open a location menu and click "Add cameras" button '''

import logging
from typing import Iterable
from typing import Sequence

from typing_extensions import Self
from typing_extensions import override
import allure

from tools.cameras import get_camera_by_name
from tools.cameras import mark_camera_as_changed

from pages.confirm_dialog import ConfirmDialog
from pages.input_field import SearchInput
from pages.camera_picker_v0_48_4 import CameraCheckbox_v0_48_4

log = logging.getLogger(__name__)


class AddCamerasDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Cameras',
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            is_mui=False,
            *args, **kwargs,
        )

    @property
    def input_search(self) -> SearchInput:
        return SearchInput(
            x_root=self.x_root,
            driver=self.driver,
            label='Search',
        )

    def search(self, query: str) -> None:
        pass

    def _iter_cameras(self) -> Iterable[CameraCheckbox_v0_48_4]:
        for element in self.get_objects(self.x_root + "//div[@class='UIWidgetBody']/div/div[contains(@class, 'UITreeCamera')]"):
            yield CameraCheckbox_v0_48_4(
                xpath=element.xpath_list,
                driver=self.driver,
            )

    def get_camera(self, camera_name: str) -> CameraCheckbox_v0_48_4:
        with allure.step(f'{self}: look for {camera_name}'):
            log.info(f'{self}: look for {camera_name}')
            for camera in self._iter_cameras():
                if camera.name == camera_name:
                    return camera
            raise RuntimeError(f'Not found {camera_name}')

    @property
    def schema(self) -> Sequence[str]:
        schema_ = []
        for camera in self._iter_cameras():
            schema_.append(
                f'{camera.name} {"☑" if camera.is_checked() else "☐"}'
            )
        return schema_

    @override
    def confirm(self, *args, **kwargs):
        log.info('Mark selected cameras as changed since disabled cameras become enabled in case user bind them to loc')
        changed_cameras = [get_camera_by_name(self.driver.client, cam.name) for cam in self._iter_cameras() if cam.is_checked()]
        [mark_camera_as_changed(cam) for cam in changed_cameras]
        super().confirm(*args, **kwargs)

    def select_cameras(self, *camera_names: Iterable[str]) -> Self:
        with allure.step(f'{self}: select {camera_names}'):
            log.info(f'{self}: select {camera_names}')
            for name in camera_names:
                self.get_camera(name).select()
            return self
