from functools import partial
import logging
import traceback
from argparse import Namespace

from requests.exceptions import HTTPError
from selenium.common.exceptions import TimeoutException
from urllib3.exceptions import MaxRetryError
import allure
import pytest

import consts
from tools import RequestStatusCodeException
from tools import attach_screenshot
from tools import config as cfg  # import as `cfg` to prevent conflict with parameter `config` `in pytest_configure`
from tools import generate_id_from_time
from tools import join_url
from tools.client import ApiClient
from tools.gitlab_integration import get_issue_by_path
from tools.gitlab_integration import skip_if_opened
from tools.gitlab_integration import url_to_path
from tools.licenses import request_demo_license
from tools.mailinator import Inbox
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.users import create_user_and_company
from tools.users import delete_company
from tools.users import delete_user_from_company
from tools.users import generate_company_name
from tools.users import get_available_companies
from tools.users import get_company_by_name
from tools.users import get_spc_admin
from tools.users import init_client
from tools.users import set_active_company
from tools.version import AppVersion
from tools.version import UnableGetAppVersion
from tools.version import get_app_version

log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def session_options() -> Namespace:
    """ pytest optins as fixture """
    return cfg.pytest_options


@pytest.fixture(scope='session')
def user_options():
    """ pytest optins as fixture """
    return cfg.user_config


@pytest.fixture(scope='session')
def env_setup(session_options):
    log.info(f"Env: {cfg.environment}")
    log.info(f"Web url: {cfg.web_url}")
    log.info(f"App version: {cfg.app_version}")
    return cfg.user_config[cfg.environment]


@pytest.fixture(scope='session')
def default_pwd():
    return cfg.user_config['_default_pwd']


@pytest.fixture(scope='module')
def client_data_created(session_options, default_pwd):
    inbox = Inbox(env=cfg.environment, iname=generate_id_from_time())

    yield {
        'email': inbox.email,
        'first_name': 'fname',  # TODO: let's generate fake name
        'last_name': 'lname',   # TODO: let's generate fake last name
        'password': default_pwd,
        'company_name': generate_company_name(),
    }


@pytest.fixture(scope='session')
def client_data_service_provider(default_pwd, env_setup):
    yield {
        'email': EmailType(env_setup["service_provider"]["email"]),
        'first_name': 'Autotest',
        'last_name': 'User',
        'password': default_pwd,
        'company_name': env_setup['service_provider']['company_name'],
    }


@pytest.fixture(scope='session')
def client_data_verified_user(default_pwd):
    yield {
        'email': 'autotest2@metapixteam.testinator.com',
        'first_name': 'Vladimir',
        'last_name': 'Lenin',
        'password': default_pwd,
        'company_name': 'TestCompanyForLicenseServerTests',
    }


@pytest.fixture(scope='session')
def client_data_integrator(default_pwd):
    yield {
        'email': EmailType('integrator2@metapixteam.testinator.com'),
        'first_name': 'Inte',
        'last_name': 'Grator',
        'password': default_pwd,
        'company_name': 'QA Team',
    }


@pytest.fixture(scope='module')
def is_demo_license_required():
    return True


@pytest.fixture(scope='module')
def client(
        session_options,
        client_data_created: dict[str, str],
        is_demo_license_required: bool,
        default_pwd: str,
):
    """ Client for generated user """
    if session_options.user_email:
        inbox = Inbox(env=cfg.environment, email=session_options.user_email)
        client = init_client(
            ApiClient(),
            email=inbox.email,
            password=session_options.user_password or default_pwd,
            company_name=session_options.user_company,
        )
    else:
        inbox = Inbox(
            env=cfg.environment,
            email=EmailType(client_data_created['email']),
        )
        create_user_and_company(
            email=inbox.email,
            company_name=CompanyNameType(client_data_created['company_name']),
        )
        client = init_client(
            client=ApiClient(),
            email=inbox.email,
            password=default_pwd,
            company_name=CompanyNameType(client_data_created['company_name']),
        )
        if is_demo_license_required:
            request_demo_license(client)

    yield client

    try:
        inbox.clear()
    except HTTPError as exc:
        log.error(f'Failed to clear inbox due to {exc}')

    if not session_options.user_email:
        with allure.step(f'Delete {client.user} and it companies'):
            log.warning(f'Delete {client.user} and it companies')

            with allure.step('Delete non active companies'):
                log.warning('Delete non active companies')
                for company in get_available_companies(client):
                    if company.name != client.company.name:
                        delete_company(client, company)

            with allure.step(f'Delete {client.user} from active company'):
                log.warning(f'Delete {client.user} from active company')
                admin = get_spc_admin()
                set_active_company(admin, client.company)
                delete_user_from_company(admin, client.user, client.company)

            with allure.step(f'Delete {client.company}'):
                delete_company(admin, client.company)


@pytest.fixture(scope='module')
def verified_client(session_options, client_data_verified_user):
    """ Verified client for static user """
    inbox = Inbox(env=cfg.environment, email=EmailType(client_data_verified_user["email"]))
    create_user_and_company(inbox.email, client_data_verified_user['company_name'])
    client = init_client(
        ApiClient(),
        email=EmailType(client_data_verified_user['email']),
        password=client_data_verified_user['password'],
    )
    company = get_company_by_name(client, client_data_verified_user['company_name'])
    set_active_company(client, company)
    try:
        request_demo_license(client)
    except RequestStatusCodeException:
        log.info("demo license has already been activated")
    yield client
    inbox.clear()


@pytest.fixture(scope='module')
def client_spc(client_data_service_provider):
    client = init_client(
        ApiClient(),
        email=EmailType(client_data_service_provider['email']),
        password=client_data_service_provider['password'],
    )
    company = get_company_by_name(client, client_data_service_provider['company_name'])
    set_active_company(client, company)
    yield client


def _add_to_report(report, key="", value="", index=0):
    if not hasattr(report.longrepr, "reprtraceback"):
        return
    if not key and not value:
        message = "\n"
    else:
        message = f'{key}: {value}\n'
    report.longrepr.reprtraceback.reprentries[0].lines.insert(index, message)


def _report_url(report_method, driver, name):
    try:
        report_method(name, driver.current_url)
    except (TimeoutException, MaxRetryError) as e:
        log.error(f"Exception during reporting url: {e}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # All code prior to yield statement would be ran prior
    # to any other of the same fixtures defined

    outcome = yield  # Run all other pytest_runtest_makereport non wrapped hooks
    report = outcome.get_result()

    if call.excinfo:
        tb_obj = call.excinfo.tb
        stack_summary = traceback.extract_tb(tb_obj)
        tb_strings = stack_summary.format()
        tb_string = ''.join(tb_strings)
        tb_string = call.excinfo.exconly() + '\n' + tb_string

        stack_summary_locals = stack_summary.extract(traceback.walk_tb(tb_obj), capture_locals=True)
        tb_strings_locals = stack_summary_locals.format()
        tb_string_locals = ''.join(tb_strings_locals)
        tb_string_locals = call.excinfo.exconly() + '\n' + tb_string_locals

        log.info(tb_string)
        log.debug(tb_string_locals)

        _report = partial(_add_to_report, report)
        _report()
        if driver := item.funcargs.get("driver"):
            _report_url(_report, driver, "Current url")
            attach_screenshot(driver, f"{item.name}.png")
        if another_driver := item.funcargs.get("another_driver"):
            _report_url(_report, another_driver, "Shared url")
            attach_screenshot(another_driver, f"{item.name}-shared.png")
        if client := item.funcargs.get("client"):
            if client.company:
                _report("Company", f'{client.company}')
            if client.user:
                _report("User", f'{client.user}')
        if env_setup := item.funcargs.get("env_setup"):
            _report("Environment", env_setup["name"])
        return report


def pytest_addoption(parser):
    parser.addoption('--env', action='store', help='Environment name')
    parser.addoption('--user-email', required=False, default=None)
    parser.addoption('--user-password', required=False, default=None)
    parser.addoption('--user-company', required=False, default=None)
    parser.addoption('--skip-sender-tests', action='store_true', default=False)


def pytest_configure(config):
    """
    FYI: logging doesn't work here
    """
    from selenium.webdriver.remote.remote_connection import LOGGER as seleniumLogger
    from urllib3.connectionpool import log as urllibLogger

    cfg.pytest_options = config.option
    # Hide unrequired log messages
    seleniumLogger.setLevel(logging.WARNING)
    urllibLogger.setLevel(logging.WARNING)

    cfg.user_config = cfg.load_config(consts.DEFAULT_CONFIG)

    cfg.environment = config.option.env
    if cfg.environment.endswith('beta'):
        cfg.environment = cfg.environment.split('-')[0]
        cfg.is_beta = True

    if custom_web_url := getattr(config.option, 'custom_web_url').strip():
        cfg.web_url = custom_web_url.removesuffix('/')
    else:
        cfg.web_url = cfg.user_config[cfg.environment]['web_url']
        if cfg.is_beta:
            cfg.web_url = join_url(cfg.web_url, '/beta/')

    try:
        cfg.app_version = get_app_version(cfg.web_url)
    except UnableGetAppVersion:
        cfg.app_version = None


def pytest_runtest_setup(item):
    def is_dev_env(env):
        return env in ('dev-metapix', 'dev-dw', 'alphatest1')

    for marker in item.iter_markers():
        if marker.name != "allure_link":
            continue
        path = url_to_path(marker.kwargs["name"])
        skip_if_opened(path, warn_if_not_opened=False)

        issue = get_issue_by_path(path)
        fixed_at = None
        for label in issue.labels:
            label = label.replace('Fixed at ', 'Fixed at::')
            if label.startswith('Fixed at'):
                version = label.split('::')[-1]
                if version == 'dev':
                    if is_dev_env(cfg.environment):
                        log.info(f'{path} is fixed at dev. Run {item.name} due to dev environment: {cfg.environment}')
                    else:
                        pytest.skip(f'{path} is fixed at dev but current env is {cfg.environment}')
                else:
                    fixed_at = AppVersion(version)
                break

        if issue.state == "closed":
            if fixed_at is not None and fixed_at > cfg.app_version:
                pytest.skip(f'Issue {path} is fixed at the next release. '
                            f'Current release: {cfg.app_version}. Fixed at: {fixed_at}')
