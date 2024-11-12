#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import time

from tools import config
from tools import generate_id_from_time
from tools.config import get_env_data
from tools.cameras import NoMoreLicensesAvailable
from tools.cameras import create_camera
from tools.cameras import enable_camera
from tools.cameras import get_camera_by_id
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.license_server import LicenseServerAPI
from tools.license_server import get_not_activated_licenses
from tools.licenses import activate_license
from tools.licenses import request_demo_license
from tools.mailinator import Inbox
from tools.mailinator import resend_confirmation_email
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.users import create_user_and_company
from tools.users import delete_company
from tools.users import delete_user_from_company
from tools.users import filter_companies
from tools.users import generate_company_name
from tools.users import get_available_companies
from tools.users import get_company_by_name
from tools.users import get_company_users
from tools.users import get_integrator_company
from tools.users import get_random_name
from tools.users import get_spc_admin
from tools.users import init_client
from tools.users import register_user
from tools.users import set_active_company

log = logging.getLogger(__name__)
config.user_config = config.load_config("config.yaml")
logging.basicConfig(level=logging.INFO)


def request_license(client: ApiClient):
    env_setup = get_env_data()
    license_server_data = env_setup['license_server']
    lic_server_admin = LicenseServerAPI(
        license_server_data['api_url'],
        license_server_data['admin'],
    )
    available_licenses = get_not_activated_licenses(lic_server_admin)
    activate_license(client, available_licenses[0].key)


def _register_user(inbox: Inbox, password: str, company_name: CompanyNameType):
    try:
        create_user_and_company(inbox.email, company_name)
        return init_client(ApiClient(), email=inbox.email, password=password)
    finally:
        inbox.clear()


if __name__ == '__main__':
    parser = argparse.ArgumentParser("A CLI interface for image_sender")

    parser.add_argument('--env', type=str, required=True)
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--request-demo', action='store_true')
    parser.add_argument('--request-license', action='store_true')
    parser.add_argument('--add-camera', type=str)
    parser.add_argument('--email', type=str)
    parser.add_argument('--password', type=str, default=config.user_config['_default_pwd'])
    parser.add_argument('--company', type=str, default=None)
    parser.add_argument('-n', type=int, default=1)
    parser.add_argument('--object-type', type=str, default=None)
    parser.add_argument('--list-templates', action='store_true')
    parser.add_argument('--list-email', action='store_true')
    parser.add_argument('--list-cameras', action='store_true')
    parser.add_argument('--list-companies', action='store_true')
    parser.add_argument('--delete-test-data', action='store_true')
    parser.add_argument('--camera', type=str, help="Camera ID or name to send objects")
    parser.add_argument('--interval', type=float, default=0.5, help="Time between sending objects (in seconds)")
    # parser.add_argument('--add-company', type=str)
    parser.add_argument('--custom-script', type=str, default=None)
    parser.add_argument('--complete-registration', type=str, default=None)
    parser.add_argument('--full-meta', type=str, default=None,
                        help='JSON which contains meta information for object. Setting meta partly is allowed')
    args = parser.parse_args()

    # workaround for https://stackoverflow.com/questions/18608812/accepting-a-dictionary-as-an-argument-with-argparse-and-python
    args.full_meta = json.loads(args.full_meta) if args.full_meta else None

    config.environment = args.env

    if args.list_templates:
        pass

    if args.list_email:
        inbox = Inbox(env=config.environment, email=args.email)
        for msg in inbox.fetch_inbox():
            log.info(f'{msg.subject} ({msg.id})')

    if args.register:
        if args.email is None:
            log.info("--email hasn't been specified. Using a random id")
            args.email = generate_id_from_time()
        inbox = Inbox(env=args.env, email=args.email)
        client_data = {
            'email': EmailType(inbox.email),
            'first_name': 'fname',
            'last_name': 'lname',
            'password': args.password,
            'company_name': generate_company_name(),
        }
        client = _register_user(
            inbox,
            company_name=client_data['company_name'],
            password=args.password,
        )
    elif args.email:
        client = init_client(ApiClient(), email=args.email, password=args.password)
        client_data = {
            'email': EmailType(args.email),
            'first_name': 'fname',
            'last_name': 'lname',
            'password': args.password,
        }
        sender = ImageSender(client)

    if args.list_companies:
        for company in get_available_companies(client):
            log.info(company)

    if args.company:
        client_data['company_name'] = args.company
        company = filter_companies(get_available_companies(client), args.company)
        if not company:
            raise RuntimeError(f'{client} does not have company "{args.company}"')
        set_active_company(client, company)

    if args.list_cameras:
        log.info(f"Available cameras for {client}")
        for camera in sender.cameras:
            log.info(f" - {camera.name} active:{camera.active} archived:{camera.archived} id:{camera.id}")

    if email := args.complete_registration:
        company = get_company_by_name(client, args.company)
        set_active_company(client, company)
        inbox = Inbox(env=config.environment, email=email)
        inbox.clear()
        resend_confirmation_email(client, email=email)
        register_user(
            client,
            inbox,
            first_name=get_random_name('First'),
            last_name=get_random_name('Last'),
        )

    if args.request_demo:
        request_demo_license(client)

    if args.request_license:
        request_license(client)

    if args.add_camera:
        camera = create_camera(client, name=args.add_camera)
        time.sleep(3)
        if not get_camera_by_id(client, camera.id).active:
            log.warning(f'{camera} is not active')
            try:
                enable_camera(client, camera)
            except NoMoreLicensesAvailable as exc:
                log.error(f'You do not have a license and not able to patch camera: {exc}')

    if args.object_type:
        if not args.camera:
            log.error("No camera specified")
            sys.exit()
        for _ in range(args.n):
            sender.send(
                object_type=args.object_type,
                camera=args.camera,
                count=1,
                meta=args.full_meta,
                get_meta=False,
            )
            time.sleep(args.interval)

    if args.custom_script:
        log.info(f"Run script: {args.custom_script}")
        eval(args.custom_script)

    if args.delete_test_data:
        log.info('> get integrator company')
        integrator_company = get_integrator_company()

        log.info('> get spc admin')
        admin = get_spc_admin()

        log.info('> set integrator company as active for admin')
        set_active_company(admin, integrator_company)

        log.info('> get available companies')
        available_companies = get_available_companies(admin)
        log.info(f'< available {len(available_companies)} companies\n')

        log.info('> collect test companies')
        test_companies = []
        prefixes = [
            'Metapix Prominent',
            'Metapix Test ',
            'MetapixAI ',
            'Test Company ',
            'Test User Company',
            'TestRegularUserAsAdmin',
            'RegularUserAsAdmin',
            'TestUserCompany',
            'Second Secret LTD ',
        ]

        env_setup = get_env_data()
        for company in available_companies:
            if company.name == env_setup['service_provider']['company_name']:
                log.warning(f'Skip service provider company: {company}')
                continue
            if company.name == admin.company.name:
                log.warning(f'Skip integrator company: {company}')
                continue
            if any(company.name.startswith(prefix) for prefix in prefixes):
                test_companies.append(company)
        log.info(f'< collected {len(test_companies)} test companies\n')

        companies_to_delete_counter = len(test_companies)
        for company_to_delete in test_companies:
            log.info(f'> delete company: {company_to_delete}')
            users_in_company = [user for user in get_company_users(admin, company_to_delete) if user.id != admin.user.id]
            log.info(f'>> delete from company {len(users_in_company)} users')
            for user_to_delete in users_in_company:
                # TODO: check other companies which the user belongs
                if not user_to_delete.email.endswith(Inbox.dom):
                    raise RuntimeError(f'Not a test user: {user_to_delete}')
                delete_user_from_company(admin, user_to_delete, company_to_delete)
            delete_company(admin, company_to_delete)
            companies_to_delete_counter -= 1
            log.info(f'< companies left: {companies_to_delete_counter}\n')
