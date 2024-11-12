from __future__ import annotations
from copy import copy
from dataclasses import dataclass
from typing import Iterable
from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING
import logging

import allure

import consts
from tools import CompanyInfoData
from tools import CompanyRoleData
from tools import RequestStatusCodeException
from tools import UserData
from tools import config
from tools import create_company_info_data
from tools import create_company_role_data
from tools import create_user_data
from tools import generate_id_from_time
from tools import parse_api_exception_message
from tools.config import get_env_data
from tools.client import ApiClient
from tools.mailinator import Inbox
from tools.types import AddressType
from tools.types import ApiCompanyType
from tools.types import ApiUserRole
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.types import IdIntType
from tools.types import IdStrType
from tools.types import TokenType
from tools.webdriver import CustomWebDriver

if TYPE_CHECKING:
    from pages.root import RootPage

log = logging.getLogger('tools.users')
TEST_COMPANY_NAME_REFIX = 'Test Company'


@dataclass
class AuthResponse:
    access_token: TokenType
    refresh_token: TokenType
    user_id: IdStrType


class CompanyDoesNotExistException(Exception):
    pass


class UserAlreadyBelongsCompany(Exception):
    ''' If you try to invite user that had already been invited to the company '''


def get_random_name(prefix: str = 'User') -> str:
    return f'{prefix} {generate_id_from_time(random_length=4)}'


def get_active_user(client: ApiClient) -> UserData:
    response = client.request(
        'get',
        f'/{consts.SERVICE_AUTH_MANAGER}/v1/user',
        expected_code=200,
    )
    return create_user_data(response.json())


def get_user(
        client: ApiClient,
        user_id: IdStrType,
) -> UserData:
    with allure.step(f'Get user by id:{user_id}'):
        log.info(f'Get user by id:{user_id}')
        response = client.request(
            'get',
            f'/{consts.SERVICE_AUTH_MANAGER}/users/{user_id}',
            expected_code=200,
        )
        return create_user_data(response.json())


def change_user_name(
        client: ApiClient,
        first_name: str,
        last_name: str,
) -> UserData:
    with allure.step(f'Change "{client.user.first_name}" -> "{first_name}" / "{client.user.last_name}" -> "{last_name}"'):
        log.info(f'Change "{client.user.first_name}" -> "{first_name}" / "{client.user.last_name}" -> "{last_name}"')
        response = client.request(
            'patch',
            f'/{consts.SERVICE_AUTH_MANAGER}/users/{client.user.id}',
            data={
                'first_name': first_name,
                'last_name': last_name,
            },
            expected_code=200,
        )
        return create_user_data(response.json())


def change_user_state(client: ApiClient, state: dict) -> None:
    client.request(
        'post',
        f'/{consts.SERVICE_AUTH_MANAGER}/v1/users/state',
        data={"state": state},
        expected_code=200,
    )


def get_second_user(
        client: ApiClient,
        company: Optional[CompanyInfoData] = None,
        role: ApiUserRole = ApiUserRole.regular,
        new_user_email: Optional[EmailType] = None,
        look_for_suitable_users: bool = True,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
) -> UserData:
    '''
    Look for another user which belongs the same company as client
    '''
    env_data = get_env_data()
    if company is None:
        company = get_active_company(client)

    with allure.step(f'Get second user for {client}'):
        log.info(f'Get second user for {client}')

        if look_for_suitable_users:
            with allure.step('Look for suitable users'):
                users = get_company_users(client, company, exclude_client=True)
                users = list(filter(lambda x: x.email != config.user_config['integrator']['admin'], users))
                users = list(filter(lambda x: x.email != EmailType(env_data['service_provider']['email']), users))
                users = list(filter(lambda x: x.role == role, users))
                if new_user_email:
                    users = list(filter(lambda x: x.email == new_user_email, users))
        else:
            users = []

        if not users:
            log.warning(f'There are no suitable user. Invite new user into company: {company.name}')
            inbox = Inbox(env=config.environment, iname=generate_id_from_time())
            users.append(
                invite_user_to_company(
                    client,
                    email=new_user_email or inbox.email,
                    company=company,
                    role=role,
                    first_name=get_random_name(first_name or role.capitalize()),
                    last_name=get_random_name(last_name or 'User'),
                    look_for_suitable_users=False,
                )
            )
        else:
            log.info(f'Found {len(users)} suitable users in company "{company.name}": {[u.email for u in users]}')
        users[0].current_password = config.user_config['_default_pwd']
        return users[0]


def get_second_user_client(
        client: ApiClient,
        company: Optional[CompanyInfoData] = None,
        *args, **kwargs,
) -> ApiClient:
    def _auth(user, company):
        new_client = ApiClient()
        init_client(new_client, email=user.email, password=config.user_config['_default_pwd'])
        set_active_company(new_client, company)
        return new_client

    if company is None:
        company = get_active_company(client)

    user = get_second_user(client=client, company=company, *args, **kwargs)
    return _auth(user, company)


def auth_euc_regular_user_in_browser(driver: CustomWebDriver) -> None:
    '''
    Auth as regular user of EUC
    '''
    euc_regular_client = get_second_user_client(
        client=driver.client,
        role=ApiUserRole.regular,
    )
    auth_user_in_browser(
        driver,
        euc_regular_client,
    )


def auth_spc_regular_user_in_browser(driver: CustomWebDriver) -> None:
    spc_regular_client = get_second_user_client(
        client=get_spc_admin(),
        company=get_spc(),
        role=ApiUserRole.regular,
        new_user_email=EmailType('spc-regular@metapixteam.testinator.com'),
    )
    auth_user_in_browser(
        driver,
        spc_regular_client,
    )
    driver.client = spc_regular_client


def auth_ic_regular_user_in_browser(driver: CustomWebDriver) -> None:
    spc_admin = get_spc_admin()
    integrator_company = get_integrator_company()
    set_active_company(spc_admin, integrator_company)
    ic_regular_client = get_second_user_client(
        client=spc_admin,
        company=integrator_company,
        role=ApiUserRole.regular,
        new_user_email=EmailType(config.user_config['integrator']['regular']),
        first_name='Regular',
        last_name='User',
    )
    auth_user_in_browser(
        driver,
        ic_regular_client,
    )
    driver.client = ic_regular_client


def auth_euc_admin_in_browser(driver: CustomWebDriver) -> None:
    euc_admin_client = get_second_user_client(
        client=driver.client,
        role=ApiUserRole.admin,
    )
    auth_user_in_browser(
        driver,
        euc_admin_client,
    )


def set_active_company(client: ApiClient, company: CompanyInfoData) -> None:
    ''' Change client active company and modify client object'''
    with allure.step(f"Switch {client} to {company}"):
        log.info(f" - switch {client} to {company}")
        client.request(
            "patch",
            f"/{consts.SERVICE_AUTH_MANAGER}/context/active-company/",
            data={"company": company.id},
            expected_code=200,
        )
        client.set_company(company)


def auth_user_in_browser(
        driver: CustomWebDriver,
        client: Optional[ApiClient] = None,
        password: Optional[str] = None,
        company_name: Optional[CompanyNameType] = None,
        open_login_page: bool = True,
        **login_kwargs) -> RootPage:
    from pages.login import LoginPage
    from pages.login_legacy import LegacyLoginPage

    def _login_and_auth():
        if config.is_beta and open_login_page:
            login_page = LegacyLoginPage(driver, open_page=True, check_primary_element_timeout=15)
            login_page = login_page.switch_to_beta_version()
        else:
            login_page = LoginPage(driver, open_page=open_login_page, check_primary_element_timeout=15)
        return login_page.login(
            email=client.user.email,
            password=password or config.user_config['_default_pwd'],
            company_name=company_name or client.company.name,
            **login_kwargs,
        )

    if not client:
        client = driver.client
    elif id(driver.client) != id(client):
        log.warning(f'Webdriver: change client {driver.client} -> {client}')
        driver.client = client

    with allure.step(f'Auth in browser as {client}'):
        log.info(f'Auth in browser as {client}')
        return _login_and_auth()


def auth_client(
        client: ApiClient,
        email: EmailType,
        password: str,
        expected_code=200,
) -> AuthResponse:
    response = client.request(
        "post",
        f"/{consts.SERVICE_AUTH_MANAGER}/auth/",
        data={
            "login": email,
            "password": password,
        },
        headers={},
        expected_code=expected_code,
    ).json()
    response = AuthResponse(
        access_token=response['access_token'],
        refresh_token=response['refresh_token'],
        user_id=response['user_id'],
    )
    client.set_access_token(response.access_token)
    client.set_refresh_token(response.refresh_token)
    return response


def set_company(
        client: ApiClient,
        company_name: Optional[CompanyNameType] = None,
) -> None:
    '''
    Wrapper for `set_active_company`:
    Either choose the first available company or choose company by its name
    '''
    available_companies = get_available_companies(client)
    if not available_companies:
        raise RuntimeError(f'No companies available for {client}')
    if company_name:
        log.info(f'Set company by name: {company_name}')
        company = filter_companies(available_companies, company_name)
    if client.company:
        log.info(f'Set company that bound to `client` object: {client.company}')
        set_active_company(client, client.company)
    if not client.company:
        company = available_companies[0]
        log.info(f'Set first available company: {company}')
        set_active_company(client, company)


def init_client(
        client: ApiClient,
        email: EmailType,
        password: str,
        company_name: Optional[CompanyNameType] = None,
        expected_code: int = 200,
) -> ApiClient:
    with allure.step(f'Auth with {email}'):
        log.info(f"Auth with {email}")
        response = auth_client(client, email, password, expected_code)
        set_company(client, company_name)
        client.set_user(get_user(client, response.user_id))
        return client


def register_user(
        client: ApiClient,
        inbox: Inbox,
        first_name: str,
        last_name: str,
        timeout: int = 15,
):
    with allure.step(f'Register {inbox}'):
        log.info(f'Register {inbox}')
        registration_link = inbox.get_registration_link(delete_message=True, timeout=timeout)
        email_token = registration_link.split('/')[-1]
        client.request(
            'post',
            f'/{consts.SERVICE_AUTH_MANAGER}/v2/register/',
            data={
                'email': inbox.email,
                'email_token': email_token,
                'first_name': first_name,
                'last_name': last_name,
                'password': config.user_config['_default_pwd'],
            },
            expected_code=200,
        )


def invite_user_to_company(
        client: ApiClient,
        email: EmailType,
        company: CompanyInfoData,
        role: ApiUserRole,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        look_for_suitable_users: bool = False,
) -> UserData:
    if not isinstance(email, EmailType):
        # TODO: temporary check
        raise RuntimeError

    if look_for_suitable_users:
        users = get_company_users(client, company, exclude_client=True)
        users = list(filter(lambda x: x.email == email, users))
        if role:
            users = list(filter(lambda x: x.role == role, users))
        if first_name:
            users = list(filter(lambda x: x.first_name == first_name, users))
        if last_name:
            users = list(filter(lambda x: x.last_name == last_name, users))
        if users:
            log.info(f'Found suitable user: {users[0]}')
            return users[0]

    with allure.step(f"{company} <- invite new user: {email}"):
        log.info(f"{company} <- invite new user: {email}")
        response = client.request(
            "post",
            f'/{consts.SERVICE_AUTH_MANAGER}/v3/users/',
            data={
                'email': email,
                'role': role,
                'company_id': company.id,
            }
        )
        if response.status_code == 400:
            # TODO: consider error "Cannot perform specific action because there does not exist a valid use pool domain associated with the user pool"
            log.warning(f'{email} already belongs to {company} due to error: {response.json()}')
            raise UserAlreadyBelongsCompany(f'{email} {company}')
        elif response.status_code == 201:
            from tools.mailinator import Inbox
            register_user(
                client,
                Inbox(env=config.environment, email=email),
                first_name=first_name or get_random_name('First'),
                last_name=last_name or get_random_name('Last'),
            )
            # WARNING!!!
            # User id changes after registering
            # So wee must find proper user among company users
            users_ = [user for user in get_company_users(client, company) if user.email == email]
            if len(users_) != 1:
                raise RuntimeError(f'User with {email=} not found in {company}')
            return users_[0]
        elif response.status_code == 200:
            return create_user_data(response.json())
        else:
            raise RequestStatusCodeException(response.json())


def get_company_title(
        driver: CustomWebDriver,
        expected_company_name: Optional[CompanyNameType] = None,
) -> str:
    with allure.step(f'Get title of active company (user: {driver.client}'):
        log.info(f'Get title of active company (user: {driver.client})')
        driver.client.get_access_token_from_driver(driver)
        company = get_active_company(driver.client)
        if expected_company_name:
            assert expected_company_name == company.name
        return company.name


def get_active_company(client: ApiClient) -> CompanyInfoData:
    log.info(f'Get active company for {client}')
    company = create_company_info_data(
        client.request(
            'get',
            f'/{consts.SERVICE_AUTH_MANAGER}/v1/user/company',
            expected_code=200,
        ).json()
    )
    if client.company.id != company.id:
        log.error(f'Self check failed. Company name mismatch: {client.company} vs {company}')
        raise RuntimeError('Self check failed. Company name mismatch')
    return company


def get_descendant_companies(
        client: ApiClient, with_deleted: bool = False) -> Sequence[CompanyInfoData]:
    """
    Settings -> List of companies

    Returns companies returned by `get_available_companies` ('/context/available-companies/')
    plus all descendant companies
    """
    with allure.step(f'Get descendant companies (including deleted: {with_deleted}) for{client}'):
        log.info(f'Get descendant companies  (including deleted: {with_deleted}) for {client}')
        response = client.request(
            'post',
            f'/{consts.SERVICE_AUTH_MANAGER}/v1/user/companies',
            data={'filters': {'with_deleted': with_deleted}},
            expected_code=200,
        )
        companies = [create_company_info_data(company) for company in response.json()['items']]
        if not companies:
            raise RuntimeError(f'No companies were found for {client}')
        return companies


def get_available_companies(client: ApiClient) -> Sequence[CompanyRoleData]:
    """
    Returns list of companies:
     - in which user has a role
     - user can switch to
    Used by "select system" and "switch system"
    This function behavior differs from `get_descendant_companies` ('v1/user/companies/')
    """
    with allure.step(f"Get available companies for {client}"):
        log.info(f"Get available companies for {client}")
        response = client.request(
            "get", f"/{consts.SERVICE_AUTH_MANAGER}/context/available-companies/",
            expected_code=200,
        )
        return [create_company_role_data(company) for company in response.json()]


def get_second_company(
        client: ApiClient,
        role: ApiUserRole = ApiUserRole.regular,
) -> Optional[CompanyInfoData]:
    with allure.step(f'Looking for second company role={role} for {client}'):
        log.info(f'Looking for second company role={role} for {client}')
        active_company = get_active_company(client)
        companies = get_available_companies(client)
        companies = list(filter(lambda c: c.id != active_company.id, companies))
        log.info(f' - found {len(companies)} companies all but the active company')
        if not companies:
            return
        companies = list(filter(lambda c: c.role == role, companies))
        log.info(f' - found {len(companies)} companies with role={role}')
        if companies:
            log.info(f' - return company {companies[0]}')
            return companies[0]


def get_or_create_second_company(client: ApiClient, role: ApiUserRole) -> CompanyInfoData:
    ''' Look for another client company. Create such company if suitable company doesn't exist '''
    with allure.step(f'Look for or create second company for {client}'):
        log.info(f'Look for or create second company for {client}')
        if (existing_company := get_second_company(client, role=role)) is None:
            log.warning(f'Not found second company with {role=} for {client}. Create a new company')
            return add_new_company(client, role=role)
        return existing_company


def get_company_users(
        client: ApiClient,
        company: CompanyInfoData,
        exclude_client: bool = False,
) -> Sequence[UserData]:
    response = client.request(
        "post",
        f'/{consts.SERVICE_AUTH_MANAGER}/v1/company/{company.id}/users',
        data={'pagination': {'pgoffset': 0, 'pgsize': -1}},
        expected_code=200,
    )
    users = [create_user_data(data) for data in response.json()['items']]
    if exclude_client:
        users = list(filter(lambda x: x.email != client.user.email, users))
    log.info(f'{company} users: {[u.email for u in users]}')
    return users


def change_password(client: ApiClient, old_password: str, new_password: str):
    with allure.step(f'{client}: change password {old_password} -> {new_password}'):
        log.info(f'{client}: change password {old_password} -> {new_password}')
        client.request(
            "post",
            f'/{consts.SERVICE_AUTH_MANAGER}/auth/change-password/',
            data={
                'old_password': old_password,
                'new_password': new_password,
            },
            expected_code=200,
        )
        client.user.current_password = new_password


def delete_user_photo(client: ApiClient) -> None:
    with allure.step(f'{client}: delete user photo'):
        log.info(f'{client}: delete user photo')
        client.request(
            'delete',
            f'/{consts.SERVICE_AUTH_MANAGER}/user-photo/',
            expected_code=200,
        )


def delete_user_from_company(
        client: ApiClient,
        user: UserData,
        company: CompanyInfoData) -> None:
    with allure.step(f'Delete {user} from {company}'):
        log.warning(f'Delete {user} from {company}')
        client.request(
            'delete',
            f'/{consts.SERVICE_AUTH_MANAGER}/v2/company/{company.id}/users/{user.id}',
            expected_code=200,
        )


def auth_ic_admin_in_browser(driver: CustomWebDriver) -> None:
    scp_admin = copy(get_spc_admin())  # TODO: workaroud. `get_spc_admin` is cached function
    integrator_company = get_integrator_company(scp_admin)
    auth_user_in_browser(
        driver,
        scp_admin,
        company_name=integrator_company.name,
        use_search=True,
    )
    init_client(
        driver.client,
        email=scp_admin.user.email,
        password=config.user_config['_default_pwd'],
    )
    set_active_company(driver.client, integrator_company)


def auth_spc_admin_in_browser(driver: CustomWebDriver) -> None:
    scp_admin = copy(get_spc_admin())  # TODO: workaroud. `get_spc_admin` is cached function
    auth_user_in_browser(
        driver,
        scp_admin,
        company_name=CompanyNameType(get_spc().name),
    )
    init_client(
        driver.client,
        email=scp_admin.user.email,
        password=config.user_config['_default_pwd'],
    )
    set_active_company(driver.client, get_spc())


def get_spc_admin() -> ApiClient:
    env_data = get_env_data()
    client = init_client(
        ApiClient(),
        email=EmailType(env_data['service_provider']['email']),
        company_name=CompanyNameType(env_data['service_provider']['company_name']),
        password=config.user_config['_default_pwd'],
    )
    companies = get_available_companies(client)
    if not companies:
        raise RuntimeError(f'{client.user} doesn\'t have any company')
    if len(companies) > 1:
        spc = filter_companies(
            companies,
            CompanyNameType(env_data['service_provider']['company_name']))
        set_active_company(client, spc)
    return client


def get_integrator_admin() -> ApiClient:
    client = init_client(
        ApiClient(),
        email=config.user_config['integrator']['admin'],
        password=config.user_config['_default_pwd'],
    )
    if len(companies := get_available_companies(client)) > 1:
        integrator_company = filter_companies(
            companies,
            CompanyNameType(config.user_config['integrator']['company_name']),
        )
        set_active_company(client, integrator_company)
    return client


def get_company_by_name(
        client: ApiClient,
        name: CompanyNameType) -> CompanyInfoData:
    from tools import NoDataFoundException

    company = filter_companies(get_available_companies(client), name)
    if not company:
        raise NoDataFoundException(f'{client} does not have company {name}')
    return company


def get_spc() -> CompanyInfoData:
    client = get_spc_admin()
    companies = get_available_companies(client)
    env_data = get_env_data()
    spc_name = env_data['service_provider']['company_name']
    with allure.step(f'Get service provider company: {spc_name}'):
        log.info(f'Get service provider company: {spc_name}')
        spc = filter_companies(companies, spc_name)
        if spc:
            log.info(f'Service provider company has been found: {spc}')
            return spc
        raise CompanyDoesNotExistException(spc_name)


def get_integrator_company(client: Optional[ApiClient] = None) -> CompanyInfoData:
    client = client or get_spc_admin()
    integrator_company_name = config.user_config['integrator']['company_name']
    with allure.step(f'Get integrator company: {integrator_company_name}'):
        log.info(f'Get integrator company: {integrator_company_name}')
        integrator_company = get_company_by_name(
            client,
            integrator_company_name,
        )
        if integrator_company:
            log.info(f'Integrator company found: {integrator_company}')
            return integrator_company
        raise CompanyDoesNotExistException(integrator_company_name)


def create_integrator_company() -> CompanyInfoData:
    integrator_company_name = config.user_config['integrator']['company_name']
    with allure.step(f'Create integrator company: {integrator_company_name}'):
        log.info(f'Create integrator company: {integrator_company_name}')
        client_spc = get_spc_admin()
        integrator_company = create_company(
            client=client_spc,
            company_name=config.user_config['integrator']['company_name'],
            company_type=ApiCompanyType.integrator,
            parent_company_id=get_active_company(client_spc).id,
        )
        return integrator_company


def get_or_create_integrator_company() -> CompanyInfoData:
    try:
        return get_integrator_company()
    except CompanyDoesNotExistException:
        return create_integrator_company()


def invite_integrator_as_admin() -> None:
    set_active_company(get_spc_admin(), get_integrator_company())
    try:
        invite_user_to_company(
            client=get_spc_admin(),
            email=config.user_config['integrator']['admin'],
            company=get_integrator_company(),
            role=ApiUserRole.admin,
            first_name='Inte',
            last_name='Grator',
        )
    except RequestStatusCodeException as e:
        exc_data = parse_api_exception_message(e)
        if exc_data['message'] not in ("This user already belongs to this company",
                                       "An account with the given email already exists."):
            raise
        log.info(f'Integrator has already been invited into {get_integrator_company()}')
    finally:
        set_active_company(get_spc_admin(), get_spc())


def create_user_and_company(
        email: EmailType,
        company_name: CompanyNameType,
        **kwargs,  # suppress error is a password was passed
) -> None:
    integrator_company = get_or_create_integrator_company()
    # invite_integrator_as_admin()  # TODO: create users and companies on behalf of integrator
    admin = get_spc_admin()
    set_active_company(admin, integrator_company)

    log.info(f'Looking for company "{company_name}" for {admin}')
    try:
        company = filter_companies(get_available_companies(admin), company_name)
        log.info(f'Found company: {company}')
    except CompanyDoesNotExistException:
        log.warning(f'No company with name "{company_name}" has been found for {admin}')
        company = create_company(
            admin,
            company_name=company_name or generate_company_name(),
            parent_company_id=integrator_company.id,
        )
    invite_user_to_company(
        admin,
        email=email,
        company=company,
        role=ApiUserRole.admin,
        look_for_suitable_users=True,
    )


def add_new_company(
        client: ApiClient,
        company_name: Optional[CompanyNameType] = None,
        role: ApiUserRole = ApiUserRole.admin,
) -> CompanyInfoData:
    ''' Create a new company and invite user (client) into it '''
    company_name = company_name or generate_company_name()
    with allure.step(f'Invite {client.user} into "{company_name}"'):
        log.info(f'Invite {client.user} into "{company_name}"')
        integrator_company = get_integrator_company()
        client_spc = get_spc_admin()
        set_active_company(client_spc, integrator_company)
        company = create_company(
            client_spc,
            company_name=company_name,
            parent_company_id=integrator_company.id,
        )
        invite_user_to_company(
            client_spc,
            client.user.email,
            company=company,
            role=role,
        )
        return company


def create_company(
        client: ApiClient,
        company_name: Optional[CompanyNameType] = None,
        parent_company_id: IdIntType = None,
        company_type: ApiCompanyType = ApiCompanyType.user,
        contact_email: Optional[EmailType] = None,
        contact_address: Optional[AddressType] = None,
) -> CompanyInfoData:
    company_name = company_name or generate_company_name()
    if parent_company_id is None:
        parent_company_id = get_company_by_name(client, client.company.name).id
    with allure.step(f"{client}: create company: {company_name=} type={company_type} {parent_company_id=}"):
        log.info(f"{client}: create company: {company_name=} type={company_type} {parent_company_id=}")
        response = client.request(
            "post",
            f"/{consts.SERVICE_AUTH_MANAGER}/v2/company",
            data={
                'name': company_name,
                'type': company_type.value,
                'parent_company_id': parent_company_id,
            },
            expected_code=200,
        )
        return create_company_info_data(response.json())


def generate_company_name() -> CompanyNameType:
    """
    Prefixes were used in past:
     - MetapixAI
     - Metapix Test
     - Metapix Prominent
     - Second Secret
    """
    name = f'{TEST_COMPANY_NAME_REFIX} {generate_id_from_time(random_length=6)}'
    return CompanyNameType(name.replace('  ', ' '))


def filter_companies(
        companies: Iterable[CompanyInfoData],
        name: CompanyNameType,
) -> CompanyInfoData:
    # TODO: support other field: type, etc
    if not companies:
        raise RuntimeError('Got empty list of companies')
    try:
        return next(c for c in companies if c.name == name)
    except StopIteration as exc:
        raise CompanyDoesNotExistException(name) from exc


def get_user_without_company(client: ApiClient) -> UserData:
    with allure.step('Get user without company'):
        log.info('Get user without company')
        inbox = Inbox(env=config.environment, iname=generate_id_from_time())
        user = invite_user_to_company(
            client,
            email=inbox.email,
            company=client.company,
            role=ApiUserRole.regular,
            first_name=get_random_name('First'),
            last_name=get_random_name('Last'),
        )
        delete_user_from_company(client, user, client.company)
        return user


def delete_company(client: ApiClient, company: CompanyInfoData) -> None:
    with allure.step(f'Delete {company} by {client.user}'):
        log.warning(f'Delete {company} by {client.user}')
        client.request(
            'delete',
            f'/{consts.SERVICE_AUTH_MANAGER}/v1/user/companies/{company.id}/',
            expected_code=202,  # Accepted
        )
