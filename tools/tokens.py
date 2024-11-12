import logging
from dataclasses import dataclass

import allure

import consts
from tools.client import ApiClient
from tools.types import IdStrType
from tools.types import TokenType

log = logging.getLogger('tools.tokens')


@dataclass
class TokenData:
    id: IdStrType
    name: str


def get_tokens(client: ApiClient) -> list[TokenData]:
    raw_tokens = client.request(
        'get', f'/{consts.SERVICE_AUTH_MANAGER}/v1/gateway_tokens',
        expected_code=200).json()['items']
    return [
        TokenData(
            id=token['id'],
            name=token['name'],
        )
        for token in raw_tokens
    ]


def create_token(client: ApiClient, name: str) -> TokenType:
    # TODO: fix return type hint
    with allure.step(f'Create token {name}'):
        log.info(f'Create token {name}')
        token = client.request(
            'post',
            f'/{consts.SERVICE_AUTH_MANAGER}/v1/gateway_token',
            expected_code=201,
            data={'token_name': name},
        ).json()
    return token['gateway_token']


def delete_token(client: ApiClient, token: TokenData) -> None:
    with allure.step(f'Delete token {token}'):
        log.info(f'Delete token {token}')
        client.request(
            'delete', f'/{consts.SERVICE_AUTH_MANAGER}/v1/gateway_token/{token.id}',
            expected_code=204,
        )


def refresh_token(client: ApiClient) -> dict:
    log.info(f'Refresh access token for {client}')
    response = client.request(
        "post", f'/{consts.SERVICE_AUTH_MANAGER}/auth/refresh-token/',
        expected_code=200,
        headers={
            'access-token': client.access_token,
            'refresh-token': client.refresh_token,
        },
    ).json()
    client.set_access_token(response['access_token'])
    client.set_refresh_token(response['refresh_token'])
    return response
