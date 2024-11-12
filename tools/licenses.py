import logging
from dataclasses import dataclass
from typing import Sequence
from typing import Optional

import allure

import consts
from tools import ResponseJson
from tools.client import ApiClient
from tools.license_server import LicenseServerLicenseData
from tools.license_server import parse_license_data
from tools.types import IdStrType

log = logging.getLogger(__name__)


@dataclass
class LicenseData:
    id: IdStrType
    cameras_count: int
    is_expired: bool


def request_demo_license(client: ApiClient, expected_code: int = 200) -> ResponseJson:
    with allure.step(f"Request demo for {client}"):
        log.info(f"Request demo for {client}")
        response = client.request(
            "get",
            f"/{consts.SERVICE_AUTH_MANAGER}/demo-licenses/",
            expected_code=expected_code,
        )
        return response.json()


def get_activated_licenses(client: ApiClient) -> Sequence[LicenseData]:
    '''
    Response item example:
    {
        "pagination":{"offnset":0,"size":4,"amount":4},
        "items":[
            {
                "id":"59b0f984-2da0-483c-9495-b8603948a451",
                "days":2,
                "cameras_count":2,
                "activated_at":"2024-06-10T11:05:38.263498+00:00",
                "expired_at":"2024-06-12T11:05:38.263506+00:00",
                "trial":false,
                "is_enabled":true,
                "is_expired":false
            }
        ],
        "cameras_count":{"total_cameras":593,"total_in_use":4}
    }
    '''
    def _get_licenses(pgoffset: int, pgsize: int, amount: Optional[int]) -> list[LicenseData]:
        if amount is not None:
            if pgoffset > amount:
                log.info(f'Get licenses: stop requesting licenses: pgoffset={pgoffset}, {amount=}')
                return []
        log.info(f'Get licenses: request licenses: {pgoffset=}')
        response = client.request(
            'post',
            f'/{consts.SERVICE_AUTH_MANAGER}/v1/licenses',
            data={'pagination': {'pgoffset': pgoffset, 'pgsize': pgsize}},
            expected_code=200,
        ).json()
        if amount is None:
            amount = response['pagination']['amount']
        return [
            LicenseData(
                id=item['id'],
                cameras_count=item['cameras_count'],
                is_expired=item['is_expired'],
            )
            for item in response['items']
        ] + _get_licenses(pgoffset+pgsize, pgsize, amount)
    with allure.step(f'Request activated licenses for {client}'):
        log.info(f'Request activated licenses for {client}')
        return _get_licenses(0, 128, None)


def activate_license(client: ApiClient, key: IdStrType) -> LicenseServerLicenseData:
    with allure.step(f'Activate license "{key}" for {client.user}'):
        log.info(f'Activate license "{key}" for {client.user}')
        response = client.request(
            'patch',
            f'/{consts.SERVICE_AUTH_MANAGER}/licenses/{key}',
            expected_code=200,
        ).json()
        return parse_license_data(response)
