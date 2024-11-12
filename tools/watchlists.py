import logging
from dataclasses import dataclass
from typing import Iterable
from typing import Optional
from typing import NewType
from typing import Mapping

import allure

import consts
from tools import ResponseJson
from tools.client import ApiClient
from tools.types import BaseType
from tools.types import IdIntType
from tools.types import LicPlateType

log = logging.getLogger('tools.watchlists')
PredicateType = NewType('PredicateType', Mapping[str, str | int])


@dataclass
class WatchListData:
    id: IdIntType
    object_type: BaseType
    name: str


def _create_watchlist_data(data: dict) -> WatchListData:
    return WatchListData(
        id=data['id'],
        object_type=data['object_type'],
        name=data['name'],
    )


def get_watchlists(client: ApiClient) -> Iterable[WatchListData]:
    response = client.request(
        'post',
        '/watchlist-manager/v1/company-watchlists',
        data={'pagination': {'pgoffset': 0, 'pgsize': -1}},
        expected_code=200,
    )
    return [_create_watchlist_data(data) for data in response.json()['items']]


def create_vehicle_predicates(
        vehicle_type: Optional[str] = None,
        license_plate: Optional[LicPlateType] = None) -> PredicateType:
    predicates = {}
    if vehicle_type:
        predicates['vehicle_type'] = vehicle_type
    if license_plate:
        predicates[consts.API_LIC_PLATE] = license_plate
    if not predicates:
        raise RuntimeError
    return PredicateType(predicates)


def create_face_predicates(
        age: Optional[tuple[int, int]] = None,  # type: ignore[assignment]
        cluster_name: Optional[str] = None,     # type: ignore[assignment]
        gender: Optional[str] = None,           # type: ignore[assignment]
) -> PredicateType:
    predicates = {}
    gender_to_code = {'male': 1, 'female': 2}   # FYI: since 0.48.3 we use integers instead of strings
                                                # (https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1470#note_77387)
    if age:
        predicates['person_age'] = list(age)
    if cluster_name:
        predicates['name'] = cluster_name
    if gender:
        predicates['person_gender'] = gender_to_code[gender]
    if not predicates:
        raise RuntimeError
    return PredicateType(predicates)


def add_predicates(
        client: ApiClient,
        watchlist: WatchListData,
        predicates: PredicateType) -> ResponseJson:
    with allure.step(f'Create a filter for {watchlist}: {predicates}'):
        response = client.request(
            'post',
            '/watchlist-manager/v1/predicates',
            data={
                'watchlist_id': watchlist.id,
                'filter': predicates,
            },
            expected_code=201,
        )
        return response.json()


def delete_watchlist(
        client: ApiClient,
        watchlist: WatchListData) -> None:
    with allure.step(f'Delete {watchlist}'):
        log.info(f'Delete {watchlist}')
        client.request(
            'delete',
            f'/watchlist-manager/v1/watchlists/{watchlist.id}',
            expected_code=200,
        )


def create_watchlist(
        client: ApiClient,
        name: str,
        object_type: BaseType) -> WatchListData:
    with allure.step(f'Create watchlist {name} of {object_type}'):
        log.info(f'Create watchlist {name} of {object_type}')
        response = client.request(
            'post',
            '/watchlist-manager/v1/watchlists',
            data={
                'name': name,
                'object_type': object_type,
            },
            expected_code=201,
        )
        return _create_watchlist_data(response.json())
