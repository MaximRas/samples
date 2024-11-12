import logging
import time
from dataclasses import dataclass
from typing import Optional
from typing import Sequence

import allure

import consts
from tools.cameras import CameraData
from tools.cameras import get_camera_by_name
from tools.cameras import get_cameras
from tools.client import ApiClient
from tools.types import IdStrType

log = logging.getLogger('tools.locations')


@dataclass
class LocationData:
    id: IdStrType
    name: str
    child_locations: list   # list of LocationData

    def __str__(self):
        return f'Location {self.name}'


def _create_location_data(data, look_for_childs=False):
    loc = LocationData(
        id=data['id'],
        name=data['name'],
        child_locations=[],
    )
    if look_for_childs and data['child_locations']:
        for child_data in data['child_locations']:
            loc.child_locations.append(
                _create_location_data(child_data, look_for_childs=True)
            )
    return loc


def get_locations(client: ApiClient) -> list[LocationData]:
    with allure.step(f"Get locations for {client}"):
        log.info(f"Get locations for {client}")
        locations = client.request(
            "get", f"/{consts.SERVICE_DEVICE_MANAGER}/locations",
            expected_code=200,
        ).json()
        return [_create_location_data(loc, look_for_childs=True) for loc in locations]


def create_location(
        client: ApiClient,
        name: str,
        parent_location_id: Optional[IdStrType] = None,
        coordinates: list[int] = [0, 0],
        description: str = "",
) -> LocationData:
    with allure.step(f"Create location '{name}' for {client}"):
        log.info(f"Create location '{name}' for {client}")
        response = client.request(
            "post",
            f"/{consts.SERVICE_DEVICE_MANAGER}/locations",
            expected_code=200,
            data={
                "name": name,
                "description": description,
                "coordinates": coordinates,
                "parent_location_id": parent_location_id,
            }
        ).json()
        return _create_location_data(response, look_for_childs=False)


def delete_location(client: ApiClient, loc: LocationData) -> None:
    with allure.step(f"Delete {loc}"):
        log.info(f"Delete {loc}")
        client.request(
            "delete",
            f"/{consts.SERVICE_DEVICE_MANAGER}/locations/{loc.id}",
            expected_code=202,
        )


def bind_camera_to_location_by_name(
        client: ApiClient,
        camera_name: str,
        location_name: str,
        delay: int = 3):
    with allure.step(f'Bind {camera_name} -> {location_name}'):
        log.info(f'Bind {camera_name} -> {location_name}')
        camera = get_camera_by_name(client, camera_name)
        bind_camera_to_location_by_id(client, camera.id, location_name, delay)


def bind_camera_to_location_by_id(
        client: ApiClient,
        camera_id: IdStrType,
        location_name: str,
        delay: int = 3):
    from pages.search import NoLocationException

    def _find_location_by_name(locations, name):
        log.info(f'Look for location {name} among: {[loc.name for loc in locations]}')
        for loc in locations:
            if loc.name == name:
                return loc
            if loc.child_locations:
                try:
                    return _find_location_by_name(loc.child_locations, name)
                except NoLocationException:
                    log.info(f'  -> no {name} among {loc.name} childs')
        raise NoLocationException

    time.sleep(delay)  # try to fix issue when backend doesn't return location that
                       # has just been added via web. I hope a small delay will help
    with allure.step(f"Bind '{camera_id}' -> '{location_name}'"):
        log.info(f"Bind '{camera_id}' -> '{location_name}'")
        cameras = [camera for camera in get_cameras(client) if camera.id == camera_id]
        if not cameras:
            raise RuntimeError(f"There is no camera: '{camera_id}'")

        bind_camera_to_location(
            client,
            cameras[0],
            _find_location_by_name(get_locations(client), location_name),
        )


def bind_camera_to_location(
        client: ApiClient,
        camera: CameraData,
        location: LocationData,
) -> None:
    with allure.step(f'Bind {camera} -> {location}'):
        log.info(f'Bind {camera} -> {location}')
        client.request(
            "patch",
            f'/{consts.SERVICE_DEVICE_MANAGER}/cameras/{camera.id}',
            data={'locations': [f'{location.id}']},
            expected_code=200,
        )


def split_camera_loc_path(path: str) -> Sequence[str]:
    parts = []
    for part in path.split('>'):
        parts.append(part.strip())
    if not parts:
        raise RuntimeError(f'Empty path: {path}')
    return parts
