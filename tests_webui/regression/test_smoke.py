from typing import Any
from typing import Callable
from typing import Generator
from typing import Iterable
from typing import Mapping
from urllib.parse import parse_qs
import logging

from allure import step
from seleniumwire.request import Request
import allure
import pytest

import consts
from tools import CompanyInfoData
from tools import config
from tools import fix_page_path
from tools import parse_object_type
from tools.cameras import change_analytics
from tools.cameras import disable_camera
from tools.cameras import enable_camera
from tools.cameras import get_camera_by_id
from tools.cameras import get_camera_by_name
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.mailinator import Inbox
from tools.mailinator import SUBJECT_REMOVED_FROM_COMPANY
from tools.search import search_api_v2
from tools.steps import create_any_chart
from tools.steps import create_any_widget
from tools.time_tools import Ago
from tools.tokens import create_token
from tools.types import ApiUserRole
from tools.types import WidgetType
from tools.types import ImageTemplateType
from tools.types import BaseType
from tools.types import CompanyNameType
from tools.types import TimestampType
from tools.types import TokenType
from tools.users import auth_user_in_browser
from tools.users import get_company_title
from tools.users import get_random_name
from tools.users import get_spc_admin
from tools.users import invite_user_to_company
from tools.webdriver import CustomWebDriver
from tools.webdriver import LastRequestsContext
from tools.webdriver import get_body

from pages.root import RootPage
from pages.dashboard import DashboardPage
from pages.layout.layout_listbox import LayoutPage
from pages.settings.companies import UIUserRole

from tests_webui.regression.widgets import check_delete_widget
from tests_webui.regression.widgets import check_live_feed_autorefresh

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("It should be possible to search {base}")
@pytest.mark.parametrize("base", ["face", "vehicle", "person"])
def test_search_works(
        sender: ImageSender, metapix: RootPage, base: BaseType):
    sender.check_diff_objects_count(["face", "vehicle", "person"], timeslice=None)
    assert metapix.search_count(base) == sender.objects_count(base, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Create widget, check sharing and deleting work: {widget_type}")
@pytest.mark.parametrize(
    'widget_type, object_type, kwargs', (
        pytest.param(consts.WIDGET_VALUE, "person", {}, marks=allure.story("Value")),
        pytest.param(consts.WIDGET_LIVE_FEED, "face-male", {'timeslice': None}, marks=allure.story("Live feeds")),
        pytest.param(consts.WIDGET_PIE_CHART, "vehicle-type-wagon", {}, marks=allure.story("Pie charts")),
        pytest.param(consts.WIDGET_LINE_CHART, "face-female", {}, marks=[
            allure.story("Line charts"),
            allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/610")
        ]),
        pytest.param(consts.WIDGET_BAR_CHART, "vehicle-type-truck", {}, marks=allure.story("Bar charts")),
    ),
    ids=['value', 'live_feed', 'pie_chart', 'line_chart', 'bar_chart'],
)
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_widget_create_sharing_ui(
        metapix: RootPage,
        widget_type: WidgetType,
        sender: ImageSender,
        object_type: ImageTemplateType,
        another_driver: CustomWebDriver,
        kwargs):
    base = parse_object_type(object_type)[0]
    auth_user_in_browser(another_driver)
    sender.check_min_objects_count({object_type: 3}, **kwargs). \
        check_diff_objects_count(["face", "vehicle", "person"], **kwargs)
    # FYI: do not use api methods to create widget
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type=base)
    shared_widget = widget.share(another_driver)

    widget.assert_objects_count(sender.objects_count(base, **kwargs))
    shared_widget.assert_objects_count(sender.objects_count(base, **kwargs))


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Shared layout has the same widgets as original layout")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_shared_layout_has_same_widgets(
        metapix: RootPage, sender: ImageSender, another_driver: CustomWebDriver):
    ''' Share layout with changed widgets and check that a shared layout has the same widgets '''
    # 'create_any_widget' may create pie chart which isn't compatible with 'person' base
    sender.check_diff_objects_count(['vehicle', 'face'])
    auth_user_in_browser(another_driver)
    create_any_chart(metapix.dashboard, base='vehicle')
    create_any_chart(metapix.dashboard, base='face')

    shared_layout = metapix.layout.share(another_driver)

    # TODO: check widget position
    assert shared_layout.widgets_titles == metapix.dashboard.widgets_titles
    # shared_widget_face = shared_layout.get_widget(origin=widget_vehicle)
    # shared_widget_person = shared_layout.get_widget(origin=widget_person)


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Create layout with widget and switch layouts")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_create_widgets_on_default_and_new_layouts_and_switch_between_them(metapix: RootPage):
    with allure.step('Create widgets on default layout'):
        create_any_widget(metapix.dashboard, title='Widget #1')
        create_any_widget(metapix.dashboard, title='Widget #2')

    with allure.step('Add new layout and check it is empty'):
        new_layout = metapix.layout.add("Another layout")
        assert metapix.layout.current_layout == "Another layout"
        assert metapix.dashboard.widgets_titles == []

    with allure.step('Create widget on new layout'):
        create_any_widget(new_layout, title='Widget on new layout')
        assert metapix.dashboard.widgets_titles == ['Widget on new layout']

    with allure.step('Switch default layout and check widgets count'):
        metapix.switch_to_default_layout()
        assert metapix.layout.current_layout == LayoutPage.DEFAULT_LAYOUT_NAME
        assert metapix.dashboard.widgets_titles == ['Widget #1', 'Widget #2']


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("It should be possible to apply filters for {object_type}")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-truck", "person"])
def test_search_filter_by_cameras(
        metapix: RootPage, sender: ImageSender, object_type: ImageTemplateType):
    base = parse_object_type(object_type)[0]
    sender.check_diff_objects_count_in_cameras(
        object_type, "camera-1", "camera-2", timeslice=None)

    # only camera-1
    results_page = metapix.search(base, cameras=["camera-1"])
    assert results_page.objects_count == sender.objects_count(
        base, cameras="camera-1", timeslice=None)

    # camera-1 + camera-2
    results_page = metapix.search(base, cameras=["camera-1", "camera-2"])
    assert results_page.objects_count == sender.objects_count(
        base, cameras=["camera-1", "camera-2"], timeslice=None)


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("Correct camera names should be displayed in Device Tree")
def test_camera_name_is_correct(metapix: RootPage, sender: ImageSender):
    device_tree = metapix.open_device_tree()
    device_tree_cams = set(camera.name for camera in device_tree.unassigned_cameras)
    assert device_tree_cams == set(cam.name for cam in sender.cameras)


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to remove widget from new layout")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_delete_widget_from_new_layout(metapix: RootPage):
    widget = create_any_widget(
        metapix.layout.add('Test layout')
    )
    check_delete_widget(metapix.dashboard, widget)


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to remove widget from copied layout")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/609")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/622")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_delete_widget_from_copied_layout(metapix: RootPage):
    widget_origin = create_any_widget(metapix.dashboard)
    widget_from_copied_layout = metapix.layout.copy("Copied layout"). \
        get_widget(origin=widget_origin)

    check_delete_widget(metapix.dashboard, widget_from_copied_layout)

    with allure.step('Check the widget from original layout was not deleted'):
        metapix.switch_to_default_layout()
        assert metapix.dashboard.widgets_titles == [widget_origin.title]


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to remove widget from default layout")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_delete_widget_from_default_layout(metapix: RootPage):
    widget = create_any_widget(metapix.dashboard)
    check_delete_widget(metapix.dashboard, widget)


@allure.epic("Frontend")
@allure.suite("Help Page")
@allure.title("Testing help page works")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/882')
def test_help_page_works(metapix: RootPage):
    help_page = metapix.open_help_page()
    assert len(set(help_page.schema)) == len(list(help_page.schema))  # there are only uniq entries
    assert len(help_page.schema) > 0
    first_page_content = help_page.content
    assert help_page

    help_page.navigation[1].click()
    assert help_page.content
    assert help_page.content != first_page_content


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/notification-manager/-/issues/40")
@allure.title("Autorefresh works in live feed for persons")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_live_feed_autorefresh_person_not_shared(
        sender: ImageSender, metapix: RootPage):
    # FYI: test for vehicle and face are in test_live_feed suite
    check_live_feed_autorefresh(metapix, "person", sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("It is possible to expand widget via resize")
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_widget_expand_via_resize(metapix: RootPage):
    widget = create_any_widget(metapix.dashboard)

    old_coords = widget.resize(dx=300)
    assert widget.box.width > old_coords.width
    assert widget.box.height == old_coords.height

    old_coords = widget.resize(dy=200)
    assert widget.box.width == old_coords.width
    assert widget.box.height > old_coords.height


@allure.epic("Frontend")
@allure.suite("Authorization")
@allure.title("Login via DWNX cloud")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/843")
def test_login_via_dwnx_cloud_with_account_from_metapix(
        metapix: RootPage,
        env_setup: Mapping[str, Any],
        user_options: Mapping[str, Any]):
    """
    FYI: There is another scenario: when you are trying to register with email which
    doesn't exists in metapix.
    But it is too complicated to automate
    """
    login_page = metapix.logout()
    login_page.driver.client = get_spc_admin()
    if env_setup.get("theme") == "nx":
        metapix = login_page.authorize_via_nx()
    elif env_setup.get("theme") == "dw":
        metapix = login_page.authorize_via_dw()
    else:
        metapix = login_page.authorize_via_dwnx()

    assert metapix.parsed_url.path == fix_page_path(DashboardPage.path)
    avatar_menu = metapix.open_avatar_menu()
    assert avatar_menu.company_name == env_setup['service_provider']['company_name']
    assert avatar_menu.user_name == user_options['DWNX']['name']


@pytest.fixture(scope="function")
def use_gateway_token(client: ApiClient) -> Generator[TokenType, None, None]:
    old_token = client.access_token

    def _use_token_func() -> None:
        with allure.step('Getting gateway token'):
            gateway_token = create_token(client, 'New Gateway Token')
            client.set_access_token(gateway_token)

    yield _use_token_func
    # restore auth token
    client.set_access_token(old_token)


@allure.epic("Backend")
@allure.suite("Authorization")
@allure.title("Plugin authorization by tokens")
@pytest.mark.usefixtures("teardown_delete_tokens")
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_disable_analytics_for_cameras')
def test_plugin_authorization_by_token(client: ApiClient, use_gateway_token: Callable):
    camera = get_camera_by_name(client, 'camera-4')
    with allure.step('Disable camera-4 and disable face analytics for the former camera with auth token'):
        disable_camera(client, camera)
        change_analytics(client, camera, 'face', False)

    with allure.step('Check it is possible to enable camera with gateway token'):
        use_gateway_token()
        enable_camera(client, camera)
        assert get_camera_by_id(client, camera.id).active is True

    with step('Check it is possible to enable face analytic with gateway token'):
        change_analytics(client, camera, 'face', True)
        assert next(filter(lambda x: x["id"] == "face", get_camera_by_id(client, camera.id).analytics))["enabled"] is True


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("It should be possible to switch company")
def test_simple_switch_company(
        metapix: RootPage,
        driver: CustomWebDriver,
        client: ApiClient,
        second_company: CompanyInfoData):
    metapix.logout().login()

    with step('Check company title is correct (before switch)'):
        floating_menu = metapix.open_avatar_menu()
        assert floating_menu.company_name == get_company_title(driver, client.company.name)
        metapix.close_avatar_menu()

    # It is possible to switch company
    metapix.switch_company(). \
        select_by_name(second_company.name)
    with step('Check company title is correct (after switch)'):
        metapix.open_avatar_menu()
        assert floating_menu.company_name == get_company_title(driver, second_company.name)


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("User receives an email in case he is added/removed from the company")
def test_email_registration_deleting_and_author(
        metapix: RootPage, client: ApiClient, inbox: Inbox):
    def check_email_by_subj(inbox: Inbox, expected_subj: str):
        with allure.step(f'Check {inbox} has mail: {expected_subj}'):
            subjects = {email.subject for email in inbox.fetch_inbox()}
            assert expected_subj in subjects, f'Subjects: {subjects}'

    with allure.step('Create a new user and add it to the company'):
        inbox = inbox.create_new()
        second_user = invite_user_to_company(
            client,
            email=inbox.email,
            company=client.company,
            role=ApiUserRole.regular,
            first_name=get_random_name('First'),
            last_name=get_random_name('Last'),
        )
        users_page = metapix.open_settings(). \
            open_users(client)
        # FYI: this check is surplus since `complete_registration_ui` checks subject and then deletes mail
        # check_email_by_subj(inbox, SUBJECT_USER_ADDED_TO_COMPANY)

    with allure.step(f'Delete {second_user.email} from {client.company}'):
        users_page.pages.set_value(consts.PAGINATION_MAX)
        message_count_before = inbox.messages_count
        users_page.get_user(inbox.email). \
            open_delete_dialog(). \
            confirm()
        inbox.wait_new_message(metapix.waiter, message_count_before)
        check_email_by_subj(inbox, SUBJECT_REMOVED_FROM_COMPANY)

    with allure.step('Check all email have the same author: "Metapix Cloud"'):
        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/miscellaneous/admin/-/issues/333
        for email in inbox.fetch_inbox():
            assert email.author == 'Metapix Cloud'


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Company name in email body is correct')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/auth-manager/-/issues/220')
def test_check_company_name_is_correct(
        metapix: RootPage, inbox: Inbox, second_company: CompanyInfoData):
    def check_company_name_is_correct(inbox: Inbox, expected_company_name: CompanyNameType):
        with allure.step(f'Check message body: make sure company name is "{expected_company_name}"'):
            msg = inbox.find_message_by_subject('You have been added to the company.')
            body = inbox.fetch_mail(msg.id)
            assert body.startswith(f'You have been added to the company {expected_company_name}')

    companies_page = metapix.open_settings(). \
        open_companies()
    with allure.step(f'Invite a new user into second company: {second_company.name}'):
        users = companies_page.get(second_company.name).open_users()
        new_user_inbox = inbox.create_new()
        users.add_user(
            role=UIUserRole.REGULAR,
            email=new_user_inbox.email)
    check_company_name_is_correct(new_user_inbox, second_company.name)


def check_timestamps_are_close(
        timestamp: TimestampType,
        expected_timestamp: TimestampType,
        delete_extra_zeros: bool):
    '''
    FYI: By unknown reason timestamp from request has 3 extra zeroes
    https://metapix-workspace.slack.com/archives/C03KLML128L/p1713160803989079
    '''
    if delete_extra_zeros is True:
        timestamp //= 1000
    diff = timestamp - expected_timestamp
    if abs(diff) > 60*5:
        pytest.fail(f'Too big diff between timestamps: {diff}')


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Check timestamps in api requests sent by search')
@pytest.mark.parametrize(
    'date_1,date_2',
    [
        (Ago('-2d'), Ago('-1d')),
    ],
    ids=['face-2d-1d'],
)
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_getting_object_timestamps_search(
        metapix: RootPage, date_1: Ago, date_2: Ago):
    def get_timestamp_filters(requests: Iterable[Request]) -> Mapping[str, TimestampType]:
        if len(requests) > 1:
            log.warning(f'Too many requests: {len(requests)}')
        for req in requests:
            req = get_body(req)
            if 'timestamp_filters' in req:
                return req['timestamp_filters']
        raise RuntimeError('No request with timestamp_filters found')
    search_panel = metapix.open_search_panel()
    search_panel.set_filters(
        {consts.FILTER_START_PERIOD: date_1.dt} |
        {consts.FILTER_END_PERIOD: date_2.dt},
    )
    with LastRequestsContext(metapix.driver) as get_last_req_func:
        search_panel.get_results(fetch_more=False, ignore_no_data=True)
        requests = get_last_req_func(url='v2/search/face')

    timestamps_search = get_timestamp_filters(requests)
    check_timestamps_are_close(timestamps_search['timestamp_start'], date_1.timestamp, True)
    check_timestamps_are_close(timestamps_search['timestamp_end'], date_2.timestamp, True)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Check timestamps in api requests sent by chart widgets')
@pytest.mark.parametrize(
    'date_1,date_2',
    [
        (Ago('-2d'), Ago('-1d')),
    ],
    ids=['face-2d-1d'],
)
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_getting_object_timestamps_chart_widgets(
        metapix: RootPage, date_1: Ago, date_2: Ago):

    def to_dict(filters: Iterable[str]) -> Mapping[str, Any]:
        result = {}
        for item in filters:
            key, value = item.split(':')
            if key.startswith('timestamp'):
                value = int(value)
            result[key] = value
        return result

    widget = create_any_chart(metapix.dashboard, base='face')
    custom_timeslice_dialog = widget.open_custom_timeslice()
    custom_timeslice_dialog.set_dates(date_1.dt, date_2.dt)
    with LastRequestsContext(metapix.driver) as get_last_req_func:
        custom_timeslice_dialog.submit()
        requests = get_last_req_func(url='chartilla/chart')
        # TODO: 3 requests is being sent after clicking "Submit". WHY!?!?!?!
    filters = to_dict(parse_qs(requests[-1].url)['filters'])
    check_timestamps_are_close(filters['timestamp_start'], date_1.timestamp, False)
    check_timestamps_are_close(filters['timestamp_end'], date_2.timestamp, False)


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Search by Object ID')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1410')
@pytest.mark.parametrize('base', ['face'])
def test_v2_search_by_identifier(
        metapix: RootPage, sender: ImageSender, base: BaseType):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    search_panel = metapix.open_search_panel(). \
        set_search_objective(consts.SEARCH_OBJECTIVE_ID)
    obj = search_api_v2(sender.client, base).get_first()

    search_panel.set_filters({consts.FILTER_OBJECT_ID: obj.id})
    results = search_panel.get_results()
    assert len(results.thumbs) == 1
    assert results.thumbs[0].id == obj.id


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Check it is possible to send feedback by user')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1449')
@pytest.mark.skip('Make sure the issue have being created in sentry')
def test_feedback(metapix: RootPage):
    if config.environment not in consts.ENV_PRODS:
        pytest.skip('Only for prod envs')
    feedback_dialog = metapix.open_feedback_dialog()
    with LastRequestsContext(metapix.driver) as get_last_req_func:
        feedback_dialog.send_feedback('Test feedback')
        requests = get_last_req_func(url='sentry.io/')
    assert len(requests) > 0


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('In new session object page is being opened after login instead of Dashboard')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/661')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1168')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1453')
def test_object_page_url_is_being_opened_in_unauthorized_session(
        metapix: RootPage, sender: ImageSender):
    with allure.step('Look for and open suitable object'):
        sender.check_min_objects_count({'face': 1}, timeslice=None)
        obj = search_api_v2(sender.client, 'face').get_first()
        object_card = metapix.open_object(obj.id)
        object_url = object_card.url

    with allure.step('Log out and open object url'):
        metapix.logout()
        metapix.open(object_url)

    with allure.step('Perform login and check there is no "switch company" dialog'):
        auth_user_in_browser(
            metapix.driver,
            open_login_page=False,         # login page had already opened
            ignore_choosing_company=True,  # company id is in object_url
        )

    with allure.step('Check that correct object has been opened'):
        assert metapix.url == object_url
        assert object_card.id == obj.id
