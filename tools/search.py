import logging
from copy import deepcopy
from typing import Sequence
from typing import Optional

import allure

import consts
from tools.getlist import GetList
from tools import ObjectData
from tools import json_to_object
from tools import parse_object_type
from tools.client import ApiClient
from tools.types import IdStrType
from tools.types import ImageTemplateType
from tools.types import FiltersType
from tools.users import change_user_state

log = logging.getLogger('tools.search')


def _parse_template(object_type: ImageTemplateType, **kwargs) -> FiltersType:
    attribute = parse_object_type(object_type)[1]
    filters: dict[str, str] = dict()
    attribute_to_filter = {
        'male': consts.API_MALE,
        'female': consts.API_FEMALE,
        'color-black': consts.API_BLACK,
        'color-yellow': consts.API_YELLOW,
        'color-white': consts.API_WHITE,
        'type-sedan': consts.API_SEDAN,
        'type-suv': consts.API_SUV,
        'type-minivan': consts.API_MINIVAN,
        'type-hatchback': consts.API_HATCHBACK,
        'type-truck': consts.API_TRUCK,
        'type-wagon': consts.API_WAGON,
        'with-beard': consts.API_BEARD,
        'with-glasses': consts.API_GLASSES,
        'with-mask': consts.API_MASK,
        'manufacturer-nissan': consts.API_NISSAN,
    }
    if attribute:
        filters.update(attribute_to_filter[attribute])
    filters.update(kwargs)
    log.debug(f'Parse template {object_type} kwargs:{kwargs} -> {filters}')
    return filters


def search_api_v2(
        client: ApiClient,
        object_type: ImageTemplateType,
        filters: FiltersType = consts.API_GOOD_QUALITY,
        pgsize: int = 100,
        pgoffset: int = 0,
        order: Optional[FiltersType] = None,
        camera_id: Optional[Sequence[IdStrType]] = None,
        location_id: Optional[Sequence[IdStrType]] = None,
        recursive: bool = False,
) -> GetList[ObjectData]:
    # TODO: improve type hints (more strict)
    def _repr_filters(filters):
        filters = deepcopy(filters)
        for key in filters.copy():
            if isinstance(filters[key], dict):
                filters[key] = _repr_filters(filters[key])
            if not filters[key]:
                del filters[key]
        return filters

    base = parse_object_type(object_type)[0]
    filters = dict(filters)
    order = order or {}  # or consts.API_ORDER_DATE_DESC
    camera_id = camera_id or []
    location_id = location_id or []

    if 'image_quality' not in filters:
        filters |= consts.API_GOOD_QUALITY

    if filters.get('image_quality') == 'all':
        # in v2 search no value means any quality :(
        del filters['image_quality']

    type_filters = {}
    if base != 'person':
        type_filters['object_type_filters'] = _parse_template(object_type)
        type_filters['object_type_filters']['object_filter_type'] = base

    data = {
        'common_filters': filters,
        # TODO: 'timestamp_filters': timestamp_filters,
        'orderings': order,
        'pagination': {
            'pgoffset': pgoffset,
            'pgsize': pgsize,
        },
    } | type_filters

    # FYI https://metapix-workspace.slack.com/archives/C03L8340TBJ/p1724750942554269?thread_ts=1724698817.922119&cid=C03L8340TBJ
    if camera_id or location_id:
        data['camera_filters'] = {}
        if camera_id:
            data['camera_filters']['camera'] = camera_id
        if location_id:
            data['camera_filters']['location'] = camera_id

    items = GetList([
        json_to_object(data, camera_id_field='camera_id')
        for data in client.request(
            'post',
            '/object-manager/v2/search/' + base,
            data=data,
            expected_code=200,
        ).json()['items']
    ])

    log.info(f'V2 search: found {len(items)} objects. Filters={_repr_filters(data)}')
    # TODO: return wrapped items (objects)
    if recursive:
        if len(items) < pgsize:
            return items
        if len(items) > pgsize:
            raise RuntimeError(f'Too many items in response: {len(items)}')
        return items + search_api_v2(
            client=client,
            object_type=object_type,
            filters=filters,
            pgsize=pgsize,
            pgoffset=pgoffset + pgsize,
            order=order,
            camera_id=camera_id,
            location_id=location_id,
            recursive=recursive,
        )
    return items


def change_left_panel_state(client: ApiClient, state: bool) -> None:
    with allure.step(f'Show filters panel for {client}'):
        log.info(f'Show filters panel for {client}')
        change_user_state(
            client, {
                "advancedSearch": {"leftPanel": {"open": state}}
            },
        )
