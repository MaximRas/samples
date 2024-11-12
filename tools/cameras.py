import logging
import uuid
from dataclasses import dataclass
from typing import Literal
from typing import Any
from typing import List
from typing import Deque
from collections import deque

import allure

import consts
from tools import RequestStatusCodeException
from tools import parse_api_exception_message
from tools.client import ApiClient
from tools.types import IdStrType
from tools.types import BaseType
from tools.users import change_user_state

log = logging.getLogger('tools.cameras')
CameraType = Literal['regular'] | Literal['both'] | Literal['archived']


class NoMoreLicensesAvailable(Exception):
    ''' You are trying to patch a camera without an active license '''


class CameraDoesNotExist(Exception):
    pass


@dataclass
class CameraData:
    id: IdStrType
    name: str
    active: bool
    archived: bool
    analytics: dict
    # is_new: bool   # FYI https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1712666816755649

    def __str__(self):
        return self.name


cameras_cache: List[CameraData] = []
changed_cameras: Deque[CameraData] = deque()


def create_camera_data(data):
    return CameraData(
        id=data['id'],
        name=data['name'],
        active=data['active'],
        archived=data['archived'],
        analytics=data['analytics'],
        # is_new=data['is_new'],  # FYI https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1712666816755649
    )


def get_cameras(
        client: ApiClient,
        camera_type: CameraType = "both",
) -> list[CameraData]:
    if cameras_cache:
        log.info('Get cameras from cache')
        return cameras_cache
    log.info(f'Get cameras for {client} {camera_type=}')
    cameras_raw = client.request(
        "get",
        f"/{consts.SERVICE_DEVICE_MANAGER}/cameras?cameras_type={camera_type}",
        expected_code=200,
    ).json()
    cameras_raw.sort(key=lambda x: x["name"])
    cameras = [create_camera_data(data) for data in cameras_raw]
    cameras_cache.extend(cameras)
    return cameras


def clear_cameras_cache() -> None:
    if cameras_cache:
        log.warning(' - Clear camera cache')
        cameras_cache.clear()
    else:
        log.warning(' - Camera cache is empty')


def mark_camera_as_changed(camera: CameraData) -> None:
    log.warning(f' - Mark {camera} as changed')
    is_already_marked = False
    for cam in changed_cameras:
        if cam.name == camera.name:
            is_already_marked = True
            break
    if is_already_marked:
        log.warning(f' - Already marked as changed: {camera}')
    else:
        changed_cameras.append(camera)
    clear_cameras_cache()


def get_camera_by_name(
        client: ApiClient,
        name: str,
        *args, **kwargs) -> CameraData:
    all_cameras = get_cameras(client, *args, **kwargs)
    match_cameras = [c for c in all_cameras if c.name == name]
    if not match_cameras:
        raise RuntimeError(f'No cameras with name: {name}')
    if len(match_cameras) > 1:
        raise RuntimeError(f'Several cameras with {name=}: {len(match_cameras)}')
    return match_cameras[0]


def get_camera_by_id(
        client: ApiClient,
        cam_id: IdStrType,
        *args, **kwargs) -> CameraData:
    all_cameras = get_cameras(client, *args, **kwargs)
    match_cameras = [c for c in all_cameras if c.id == cam_id]
    if len(match_cameras) != 1:
        raise RuntimeError(f'Wrong amount of cameras camera_id={cam_id}')
    return match_cameras[0]


def create_camera(
        client: ApiClient,
        name: str | None = None,
) -> CameraData:
    # TODO: make sure there is no camera with such name
    # TODO: new type: CameraId(str)
    camera_id = str(uuid.uuid4())
    name = name or f'camera-{len(get_cameras(client))+1}'
    with allure.step(f'Creating name:{name} id:{camera_id}'):
        log.info(f'Creating {name} id:{camera_id}')
        response = client.request(
            "put",
            f'/device-manager/cameras/{camera_id}',
            data={'name': name},
            expected_code=201,
        )
        return create_camera_data(response.json())


def delete_camera(client: ApiClient, camera: CameraData) -> None:
    ''' FYI: https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/415 '''
    with allure.step(f'Delete {camera}'):
        log.warning(f'Delete {camera} by {client}')
        try:
            client.request(
                'delete',
                f'/device-manager/cameras/{camera.id}',
                expected_code=202,
            )
        except RequestStatusCodeException as exc:
            exc_data = parse_api_exception_message(exc)
            if 'doesn\'t exist' in exc_data['message']:
                raise CameraDoesNotExist from exc
            raise


def delete_all_cameras_for_client(client: ApiClient) -> None:
    with allure.step(f'Delete all cameras for {client}'):
        cameras = get_cameras(client)
        if len(cameras) > 0:
            for camera in cameras:
                delete_camera(client, camera)


def enable_camera(
        client: ApiClient,
        camera: CameraData,
        **kwargs) -> CameraData:
    return patch_camera(client, camera, {'active': True}, **kwargs)


def disable_camera(
        client: ApiClient,
        camera: CameraData,
        **kwargs) -> CameraData:
    '''
    FYI: possible and implicit problem of disabling camera:
    https://metapix-workspace.slack.com/archives/C03KM08QYTE/p1680773015254079
    Possible solution: disable only rerely used camera (camera-3, camera-4)
    '''
    return patch_camera(client, camera, {'active': False}, **kwargs)


def patch_camera(
        client: ApiClient,
        camera: CameraData,
        data: dict[str, Any],
        mark_as_changed: bool = True,
) -> CameraData:
    if not data:
        raise RuntimeError('No options were specified')
    with allure.step(f'Patch {camera} -> {data}'):
        log.info(f'Patch {camera} -> {data}')

        try:
            if mark_as_changed:
                mark_camera_as_changed(camera)
            response = client.request(
                "patch",
                f'/device-manager/cameras/{camera.id}',
                data=data,
                expected_code=200,
            )
        except RequestStatusCodeException as exc:
            exc_data = parse_api_exception_message(exc)
            if 'No more licenses available' in exc_data['message']:
                raise NoMoreLicensesAvailable from exc
            if 'doesn\'t exist' in exc_data['message']:
                raise CameraDoesNotExist from exc
            raise
        return create_camera_data(response.json())


def unarchive_camera(
        client: ApiClient,
        camera: CameraData,
        **kwargs) -> CameraData:
    return patch_camera(client, camera, {'archived': False}, **kwargs)


def change_analytics(
        client: ApiClient,
        camera: CameraData,
        id: BaseType,
        enabled: bool,
        **kwargs) -> CameraData:
    data = {'analytics': [{'id': id, 'enabled': enabled}]}
    return patch_camera(client, camera, data, **kwargs)


def rename_camera(
        client: ApiClient,
        camera: CameraData,
        new_name: str,
        **kwargs) -> CameraData:
    return patch_camera(client, camera, {'name': new_name}, **kwargs)


def archive_camera(
        client: ApiClient,
        camera: CameraData,
        **kwargs) -> CameraData:
    '''
    Archive and disable camera.
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/device-manager/-/issues/104
    '''
    return patch_camera(client, camera, {'archived': True}, **kwargs)


def change_camera_panel_state(client: ApiClient, state: bool) -> None:
    with allure.step(f'Change camera panel state for {client}'):
        log.info(f'Change camera panel state for {client}')
        change_user_state(
            client, {
                "deviceTree": {"leftPanel": {"open": state}}
            },
        )
