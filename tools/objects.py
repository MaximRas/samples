from __future__ import annotations
import logging
import time
from typing import Iterable
from typing import Iterator
from typing import Sequence
from typing import Callable
from typing import TYPE_CHECKING
from collections import defaultdict

import allure

import consts
from tools.getlist import GetList
from tools import NoDataFoundException
from tools import ObjectData
from tools import ResponseJson
from tools import generate_id_from_time
from tools import json_to_object
from tools.client import ApiClient
from tools.retry import retry
from tools.search import search_api_v2
from tools.types import BaseType
from tools.types import IdIntType
if TYPE_CHECKING:
    from tools.image_sender import ImageSender
    from tools.image_sender import MetaType

log = logging.getLogger('tools.objects')


class NotEnoughClustersException(Exception):
    pass


is_head_of_cluster = lambda obj: obj.parent_id is None and obj.cluster_size > 0 and obj.is_reference is True
is_not_head_of_cluster = lambda obj: obj.parent_id is not None
is_object_without_cluster = lambda obj: obj.parent_id is None and obj.cluster_size <= 1


def get_head_objects(
        client: ApiClient,
        object_type: str,
        min_cluster_size: int = 1) -> Sequence[ObjectData]:
    objects = filter(is_head_of_cluster, search_api_v2(client, object_type, pgsize=250, recursive=True))
    return GetList(filter(lambda obj: obj.cluster_size > min_cluster_size, objects))


def get_nonhead_objects(
        client: ApiClient,
        object_type: str) -> Sequence[ObjectData]:
    ''' Non head objects which belongs to a cluster '''
    return GetList(filter(is_not_head_of_cluster, search_api_v2(client, object_type, pgsize=250, recursive=True)))


def get_objects_without_cluster(
        client: ApiClient,
        object_type: str) -> Sequence[ObjectData]:
    return GetList(filter(is_object_without_cluster, search_api_v2(client, object_type, pgsize=250, recursive=True)))


def change_cluster_name(
        client: ApiClient,
        item: ObjectData,
        name: str,
        delay: int = 2,
) -> None:
    change_metadata(client, item, {"name": name})
    item.meta['name'] = name
    time.sleep(delay)


def change_object_notes(
        client: ApiClient,
        item: ObjectData,
        notes: str,
) -> None:
    change_metadata(client, item, {"notes": notes})


def get_object(
        client: ApiClient,
        object_id: IdIntType) -> ObjectData:
    response = client.request(
        'get',
        f'/object-manager/objects/{object_id}',
        expected_code=200,
    )
    return json_to_object(response.json(), camera_id_field='camera')


def change_metadata(
        client: ApiClient,
        item: ObjectData,
        new_meta: MetaType,
) -> ResponseJson:
    with allure.step(f"Change meta for {item}"):
        old_meta = {m: item.meta[m] for m in new_meta}
        log.info(f"Change meta for object {item}: {old_meta} -> {new_meta}")
        return client.request(
            "patch",
            f"/object-manager/objects/{item.id}",
            data={"metadata": new_meta},
            expected_code=201,
        ).json()


def send_single_object(sender: ImageSender, base: BaseType) -> None:
    '''
    The probles is that we from time to time requre the object without a cluster.
    We don't have such object and don't have any possibility to do it.
    So the plot is: send seldom used objects and pray we haven't sent them earlier.
    '''
    base_to_templates = {
        'face': {
            'face-with-mask': 1,
            'face-with-beard': 1,
            'face-good-quality': 1,
        },
        'vehicle': {
            "vehicle-type-suv": 1,
            "vehicle-type-van": 1,
            "vehicle-type-minivan": 1,
            "vehicle-type-unknown": 1,
        },
    }
    sender.check_min_objects_count(base_to_templates[base], timeslice=None)


@retry(NotEnoughClustersException, delay=5)
def get_suitable_objects(
        sender: ImageSender,
        bases: Iterable[BaseType],
        count: int,
        allow_single_objects: bool,
        min_cluster_size: int,
        max_cluster_size: int = 50,
) -> Sequence[ObjectData]:
    # TODO: describe
    suitable_objects: list[ObjectData] = []
    required_count = count

    for base in bases:
        suitable_objects += get_head_objects(sender.client, base, min_cluster_size=min_cluster_size)

    suitable_objects = [obj for obj in suitable_objects if obj.cluster_size <= max_cluster_size][:count]
    required_count = count - len(suitable_objects)
    log.info(f'get_suitable_objects. found head objects: {len(suitable_objects)}, required: {required_count}')

    if len(suitable_objects) < count and allow_single_objects:
        log.info(f'get_suitable_objects. not enough objects: required {required_count} more single objects')
        for base in bases:
            suitable_objects += get_objects_without_cluster(sender.client, base)
        suitable_objects = suitable_objects[:count]
        required_count = count - len(suitable_objects)
        log.info(f'get_suitable_objects. found head+single objects: {len(suitable_objects)}, required: {required_count}')

    if len(suitable_objects) != count:
        for base in bases:
            sender.send(base, count=2)
        raise NotEnoughClustersException(f'Not enough clusters of {bases}: {len(suitable_objects)}, required: {count}')
    return GetList(suitable_objects)


def get_objects_without_license_plate(sender: ImageSender) -> Iterable[ObjectData]:
    with allure.step('Look for vehicle objects without license plate'):
        objects = search_api_v2(sender.client, 'vehicle')
        objects = [o for o in objects if not o.meta['license_plate']]
        log.info(f'Objects without license plate: {len(objects)}')
        if not objects:
            raise NoDataFoundException
        return iter(objects)


def _get_object_with_license_plate(
        sender: ImageSender,
        predicate: Callable[[int], bool]) -> Iterator[ObjectData]:
    objects = search_api_v2(sender.client, 'vehicle')
    objects_with_lic_plate = [o for o in objects if o.meta['license_plate']]
    log.info(f'Objects with license plate: {len(objects_with_lic_plate)}')
    lic_to_obj = defaultdict(list)
    for obj in objects_with_lic_plate:
        lic_to_obj[obj.meta['license_plate']].append(obj)
    for lic_plate, objects in lic_to_obj.items():
        log.info(f'{lic_plate} belongs to {len(objects)} vehicles')
        if predicate(len(objects)):
            return iter(objects)
    raise NoDataFoundException


def get_object_with_uniq_license_plate(sender: ImageSender) -> ObjectData:
    with allure.step('Look for vehicle object wiht uniq license plate'):
        objects = _get_object_with_license_plate(sender, lambda length: length == 1)
        if objects:
            return next(objects)
        sender.send('vehicle', meta={consts.META_LIC_PLATE: generate_id_from_time()})
        return get_object_with_uniq_license_plate(sender)


def get_objects_with_non_equal_license_plate(sender: ImageSender, min_amount: int = 2) -> Iterable[ObjectData]:
    with allure.step('Look for vehicle with non-equal license plate (there are other vehicles with the same license plate'):
        objects = _get_object_with_license_plate(sender, lambda length: length >= min_amount)
        if objects:
            return objects
        sender.send('vehicle', count=min_amount, meta={consts.META_LIC_PLATE: generate_id_from_time()})
        return get_objects_with_non_equal_license_plate(sender)
