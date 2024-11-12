import logging
from dataclasses import dataclass
from typing import Sequence
from typing import TypedDict

import allure

import consts
from tools import ResponseJson
from tools.client import ApiClient
from tools.types import IdStrType

log = logging.getLogger('tools.layouts')


class GridItemType(TypedDict):
    h: int
    w: int
    x: int
    y: int
    id: IdStrType


@dataclass
class LayoutData:
    id: IdStrType
    name: str
    shared: bool
    default: bool
    ordering: int
    user_id: IdStrType
    grid: list[GridItemType]

    def __str__(self):
        return f'Layout "{self.name}"'


def _create_layout(data):
    return LayoutData(
        id=data['id'],
        name=data['name'],
        shared=data['shared'],
        default=data['default'],
        grid=data.get('grid', None),
        user_id=data.get('user_id', None),
        ordering=data.get('ordering', None)
    )


def delete_layout(client: ApiClient, layout: LayoutData) -> ResponseJson:
    with allure.step(f"Delete {layout}"):
        log.info(f"Delete {layout}")
        return client.request(
            "delete",
            f"/{consts.SERVICE_LAYOUT_MANAGER}/v1/layouts/{layout.id}",
            expected_code=200,
        ).json()


def get_layouts(client: ApiClient) -> Sequence[LayoutData]:
    '''
    Response doesn't have 'user_id', 'grid', and 'ordering' compared to `get_layout`
    '''
    raw_layouts = client.request(
        "get",
        f"/{consts.SERVICE_LAYOUT_MANAGER}/v1/layouts",
        expected_code=200,
    ).json()
    layouts = [_create_layout(layout) for layout in raw_layouts]
    log.info(f'Found {len(layouts)} layouts for {client}')
    return layouts


def get_layout(client: ApiClient, layout) -> LayoutData:
    data = client.request(
        'get',
        f'/{consts.SERVICE_LAYOUT_MANAGER}/v3/layouts/{layout.id}',
        expected_code=200,
    ).json()
    return _create_layout(data)


def add_widget_to_layout(
        client: ApiClient,
        widget_id: IdStrType,
        layout: LayoutData,
) -> None:
    with allure.step(f'Add widget to layout {layout.name}'):
        log.info(f'Add widget {widget_id} to {layout}')
        grid = get_layout(client, layout).grid
        for grid_item in grid:
            log.warning(f'{layout} have item: {grid_item}')
        grid.append(
            {
                'id': widget_id,
                'x': 0,
                'y': len(grid),
                'w': 2,
                'h': 2,
            }
        )
        client.request(
            'patch',
            f'/{consts.SERVICE_LAYOUT_MANAGER}/v3/layouts/{layout.id}',
            expected_code=200,
            data={'grid': grid}
        )


def clear_layout(client: ApiClient, layout: LayoutData) -> None:
    with allure.step(f"Delete all widgets from {layout}"):
        log.info(f"Delete all widgets from {layout}")
        client.request(
            "patch",
            f"/{consts.SERVICE_LAYOUT_MANAGER}/v3/layouts/{layout.id}",
            data={'grid': [], "default": True},
            expected_code=200,
        )
