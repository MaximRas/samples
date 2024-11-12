from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from typing import Optional
from typing import Sequence
from typing import Mapping
import logging

from strenum import StrEnum
import requests
import iso8601

from tools import NoDataFoundException
from tools.types import IdStrType

log = logging.getLogger(__name__)


class LicStatus(StrEnum):
    NOT_ACTIVATED = 'not activated'


@dataclass
class LicenseServerLicenseData:
    key: IdStrType
    days: int
    cameras: int
    status: LicStatus
    trial: bool
    is_enabled: bool
    contract_id: str
    activated_at: Optional[datetime]

    def __str__(self) -> str:
        return f'License {self.key}'


def parse_license_data(item: Mapping) -> LicenseServerLicenseData:
    return LicenseServerLicenseData(
        key=item['id'],
        days=item['days'],
        cameras=item['cameras_count'],
        status=item.get('status', None),
        trial=item['trial'],
        is_enabled=item['is_enabled'],
        contract_id=item['contract_id'],
        activated_at=None if item['activated_at'] is None else iso8601.parse_date(item['activated_at']),
    )


class LicenseServerAPI:
    def __init__(self, web_url, login, password="String!2"):
        self._url = web_url
        self._login = login
        self._password = password
        self._token = self._authorize()

    def _authorize(self) -> str:
        log.info(f'Auth on license server as {self._login}')
        response = requests.post(
            f'{self._url}/public/auth/',
            json={'login': self._login, 'password': self._password},
        ).json()
        return response['access_token']

    def get_license_by_id(self, license_id: IdStrType) -> LicenseServerLicenseData:
        for lic in self.get_licenses():
            if lic.key == license_id:
                return lic
        raise NoDataFoundException(license_id)

    def get_licenses(self) -> Iterable[LicenseServerLicenseData]:
        pgoffset = 0
        pgsize = 512
        data = []

        while True:
            log.info(f'Get licenses for {pgoffset=}')
            response = requests.post(
                f'{self._url}/public/v1/licenses/',
                json={'pagination': {'pgoffset': pgoffset, 'pgsize': pgsize}},
                headers={'access-token': self._token, 'Content-Type': 'application/json'},
            ).json()
            amount = response['amount']
            pgoffset += pgsize
            for item in response['items']:
                data.append(parse_license_data(item))
            if pgoffset >= amount:
                break
        assert len(data) == amount
        return data

    @property
    def amount(self):
        licenses = self.get_licenses()
        return len(licenses)


def get_not_activated_licenses(lic_server_admin: LicenseServerAPI) -> Sequence[LicenseServerLicenseData]:
    all_licenses = lic_server_admin.get_licenses()
    not_activated = [lic for lic in all_licenses if lic.activated_at is None]
    return not_activated
