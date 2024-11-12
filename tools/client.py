import logging
from typing import Mapping
from typing import Any

import allure
import requests
from requests.models import Response
import urllib3

from tools import CompanyInfoData
from tools import RequestStatusCodeException
from tools import UserData
from tools import config
from tools.config import get_env_data
from tools.local_storage import LocalStorage
from tools.retry import retry
from tools.types import TokenType
from tools.types import UrlType
from tools.webdriver import CustomWebDriver

log = logging.getLogger(__name__)


class ApiClientException(Exception):
    pass


class YouDidNotSelectCompany(Exception):
    pass


class NetworkProblemException(requests.exceptions.RequestException):
    pass


class InternalServerErrorException(Exception):
    pass


class TokenIsExpiredException(Exception):
    pass


class BadGatewayException(Exception):
    '''502 Bad Gateway'''


class UserIsNotConfirmedException(Exception):
    '''{"code":400,"status":"error","message":"User is not confirmed. Please follow the confirmation link at your email"}'''


class UserContextCouldntBeObtainedException(Exception):
    ''' {"code":401,"status":"error","message":"User context couldn't be obtained"}'''


class ApiClient:
    def __init__(self, url=None):
        self._root_url: UrlType = url or UrlType(get_env_data()['url'])
        self._access_token: TokenType = None
        self._refresh_token: TokenType = None
        self._requests_timeout: tuple[int, int] = tuple(config.user_config['requests_timeout'])
        self._host: str = self._root_url.split('//')[1]  # TODO: parse url
        self._user: UserData = None
        self._company: CompanyInfoData = None

    @property
    def company(self) -> CompanyInfoData:
        return self._company

    @property
    def user(self) -> UserData:
        return self._user

    def copy(self, client) -> None:
        self.set_access_token(client.access_token)
        self.set_refresh_token(client.refresh_token)
        self.set_user(client.user)
        self.set_company(client.company)

    def __eq__(self, o):
        return self.user.id == o.user.id and self.company.id == o.company.id

    def __str__(self):
        if self.user and self.company:
            return f'{self.user.email}({self.company.name})'
        return 'ApiClient (not initialized yet)'

    def set_user(self, data: UserData):
        log.debug(f'Change user data {self} -> {data}')
        self._user = data

    def set_company(self, data: CompanyInfoData) -> None:
        log.debug(f'Change company data {self} -> {data}')
        self._company = data

    @property
    def access_token(self) -> TokenType:
        if self._access_token is None:
            raise ApiClientException("no access token")
        return self._access_token

    @property
    def refresh_token(self) -> TokenType:
        if self._refresh_token is None:
            raise ApiClientException("no refresh token")
        return self._refresh_token

    def get_access_token_from_driver(self, driver: CustomWebDriver) -> None:
        with allure.step(f"{self}: get access token from webdriver local storage"):
            log.info(f"{self}: get access token from webdriver local storage")
            local_storage = LocalStorage(driver)
            self.set_access_token(TokenType(local_storage.get("access-token")))
            log.debug(f"{self}: token has been changed -> {self.access_token}")

    def set_refresh_token(self, token: TokenType) -> None:
        with allure.step(f"Change refresh token {self}"):
            log.debug(f"change refresh token {self}")
            if not token:
                raise ApiClientException("empty token isn't allowed")
            self._refresh_token = token

    def set_access_token(self, new_token: TokenType) -> None:
        with allure.step(f"Change access token {self}"):
            log.debug(f"Change access token {self}")
            if not new_token:
                raise ApiClientException("empty token isn't allowed")
            self._access_token = new_token

    @retry(NetworkProblemException, delay=3, tries=3)
    @retry(InternalServerErrorException)
    @retry(TokenIsExpiredException)
    @retry(YouDidNotSelectCompany)
    def request(
            self,
            method: str,
            path_with_params: str,
            headers: Mapping[str, Any] = None,  # type: ignore[assignment]
            data: Mapping[str, Any] = None,     # type: ignore[assignment]
            expected_code: int = None,          # type: ignore[assignment]
    ) -> Response:
        from tools.tokens import refresh_token
        from tools.users import set_company

        data = data or {}
        headers = headers if headers is not None else {"access-token": self.access_token}
        url = self._root_url + path_with_params
        try:
            response = getattr(requests, method)(url, headers=headers, json=data, timeout=self._requests_timeout)
            log.debug(f'{method.upper()} {url} {response.status_code}{" Payload: " + str(data) if data else ""}')
        except (requests.exceptions.RequestException,
                urllib3.exceptions.MaxRetryError) as exc:
            log.error(f'{exc} url: {method} {url}')
            log.error(f'{exc} data: {data}')
            log.error(f'{exc} headers: {headers}')
            raise NetworkProblemException(url) from exc
        if response.status_code == 500:
            raise InternalServerErrorException(response.text)
        if response.status_code == 502:
            raise BadGatewayException(response.text)
        if response.status_code == 403:
            if 'Token is expired' in response.text:
                refresh_token(self)
                set_company(self)
                raise TokenIsExpiredException(response.text)
            if 'You did not select company' in response.text:
                set_company(self)
                raise YouDidNotSelectCompany
        if response.status_code >= 400 and 'User is not confirmed' in response.text:
            raise UserIsNotConfirmedException(f'User is not confirmed: {data["login"]}')
        if response.status_code == 401 and "User context couldn't be obtained" in response.text:
            # init_client(self, self.data)
            # set_active_company(self, get_active_company(self))
            raise UserContextCouldntBeObtainedException(response.text)
        if expected_code:
            if response.status_code != expected_code:
                raise RequestStatusCodeException(response.text)
        return response
