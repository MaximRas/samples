import time
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Callable
from typing import Generator

import allure
import pytest
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import MoveTargetOutOfBoundsException

import consts
from tools import are_dicts_equal
from tools import run_test
from tools import send_value_to_test
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.locations import bind_camera_to_location_by_name
from tools.steps import create_any_chart
from tools.steps import create_any_widget
from tools.steps import create_location_schema_api
from tools.steps import create_widget_api
from tools.steps import fill_intervals_with_objects
from tools.steps import prepare_objects_with_notes
from tools.time_tools import Ago
from tools.time_tools import change_timezone
from tools.time_tools import timedelta_hours
from tools.types import ApiUserRole
from tools.types import BaseType
from tools.types import XPathType
from tools.users import auth_user_in_browser
from tools.users import get_or_create_second_company
from tools.users import get_second_user_client
from tools.webdriver import CustomWebDriver

from pages.base_page import ElementIsNotClickableException
from pages.base_page import NoElementException
from pages.base_page import is_element_exist
from pages.root import RootPage
from pages.widgets import NotSharedWidget
from pages.widgets import NotSharedChart
from pages.widgets.builder import WidgetsBuilder
from pages.widgets.dialog_choose_type import ChooseWidgetType
from pages.widgets.pie_chart import SectorNotInteractableException

from tests_webui.regression import parse_widget_updated_date
from tests_webui.regression.widgets import check_filter_by_empty_location
from tests_webui.regression.widgets import check_autorefresh_works
from tests_webui.regression.widgets import check_change_timeslice
from tests_webui.regression.widgets import check_is_possible_to_rename_widget
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_timeslice
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_camera
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_location
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_changing_base
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_autorefresh
from tests_webui.regression.widgets import check_original_widget_and_shared_does_not_affect_each_other_legend

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@pytest.fixture(scope="function")
def client_admin(client):
    """ Another user from same company as `client` """
    return get_second_user_client(
        client=client,
        role=ApiUserRole.admin,
        first_name='Admin',
        last_name='User',
    )


@pytest.fixture(scope="function")
def second_company_admin(client_admin):
    return get_or_create_second_company(client_admin, role=ApiUserRole.admin)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Search locations in widget filter settings")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_search_locations_in_widget_filter_settings(metapix, client):
    create_location_schema_api(client, {
        "Garden": [
            {"Enterance": ['camera-1']},
            'camera-2',
        ]
    })

    widget = create_any_widget(metapix.dashboard, base='face')
    filter_dialog = widget.open_settings(). \
        open_camera_picker(). \
        expand_all_locations()

    assert filter_dialog.schema == [
        {
            '▲ Garden ☑': [
                {'▲ Enterance ☑': ['camera-1 ☑']},
                'camera-2 ☑',
            ]
        },
        'camera-3 ☑',
        'camera-4 ☑',
    ]
    assert filter_dialog.search("camera-1").schema == [
        {
            '▲ Garden ☑': [
                {'▲ Enterance ☑': ['camera-1 ☑']},
            ]
        },
    ]
    assert filter_dialog.search("Enterance").schema == [
        {
            '▲ Garden ☑': [
                {'▲ Enterance ☑': ['camera-1 ☑']},
            ]
        },
    ]
    assert filter_dialog.search("Garden").schema == [
        {
            '▲ Garden ☑': ['camera-2 ☑'],
        },
    ]
    assert filter_dialog.search("deadbeef").schema == []


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Search cameras in widget filter settings")
def test_search_cameras_in_widget_filter_settings(metapix):
    query_to_result = {
        'camera-1': ["camera-1 ☑"],
        'camera': ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☑', 'camera-4 ☑'],
        '': ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☑', 'camera-4 ☑'],
        'deadbeef': [],
    }
    widget = create_any_widget(metapix.dashboard)
    filter_dialog = widget.open_settings(). \
        open_camera_picker()

    for query, expected_result in query_to_result.items():
        assert filter_dialog.search(query).schema == expected_result


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("It is not possible to create widget without title")
def test_impossible_to_create_widget_without_title(metapix):
    """
    https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/484
    """
    builder = metapix.dashboard.open_widget_builder(). \
        choose_widget_type(consts.WIDGET_VALUE)
    builder.set_title("")
    builder.select_base("face")
    with suppress(ElementIsNotClickableException):
        builder.apply()

    assert len(metapix.dashboard.widgets_titles) == 0


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/607')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/870')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1617')
@allure.title('It should be possible to switch bar/line widget type to line/bar via header and settings')
def test_bar_line_chart_changing_widget_type_via_settings_and_header(
        metapix: RootPage, sender: ImageSender):
    '''
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/870#note_44692
    '''
    def chart_content_is_correct(widget: NotSharedChart):
        # FYI: lets count objects. this is implicitl way to check that widget content is correct:
        # (bar chart has bars and line chart has lines)
        return widget.objects_count == sender.objects_count('vehicle')

    with allure.step('Prepare objects and create widget'):
        sender.check_diff_objects_count(['face', 'vehicle', 'person'])
        widget = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, 'vehicle')

    with allure.step('Switch to "line chart" via header'):
        widget = widget.switch_to_line_chart()
        assert chart_content_is_correct(widget)

    with allure.step('Refresh dashboard and check widget type is still "line chart"'):
        metapix.refresh()
        assert widget.button_line_chart.is_highlighted()
        assert not widget.button_bar_chart.is_highlighted()
        assert chart_content_is_correct(widget)

    with allure.step('Switch to "bar chart" via widget settings'):
        widget.open_settings(). \
            switch_to_bar_chart().apply()
        widget = metapix.dashboard.get_widget(title=widget.title, widget_type=consts.WIDGET_BAR_CHART)
        assert not widget.button_line_chart.is_highlighted()
        assert widget.button_bar_chart.is_highlighted()
        assert chart_content_is_correct(widget)

    with allure.step('Refresh dashboard and check widget type is still "bar chart"'):
        metapix.refresh()
        assert not widget.button_line_chart.is_highlighted()
        assert widget.button_bar_chart.is_highlighted()
        assert chart_content_is_correct(widget)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Original widget does`t affect shared one after switch Bar -> Line for {base}')
@pytest.mark.parametrize('base', ['vehicle'])
def test_original_widget_switch_bar_line_chart_does_not_affect_shared(
        metapix: RootPage, another_driver: CustomWebDriver, base: BaseType, sender: ImageSender):
    sender.check_min_objects_count({base: 1})
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    shared_widget = widget.share(another_driver)
    shared_widget_original_state = shared_widget.state

    widget = widget.switch_to_line_chart()
    shared_widget.refresh()
    assert are_dicts_equal(shared_widget.state, shared_widget_original_state)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Cancel deleting widget")
def test_cancel_delete_widget(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type="face")
    widget.open_delete_dialog().cancel()
    assert is_element_exist(lambda: widget) is True


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Change widget name via header")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/704")
def test_change_widget_name_via_header(metapix):
    widget = create_any_widget(metapix.dashboard, 'face')
    check_is_possible_to_rename_widget(widget)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/620")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/704")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1618')
@allure.title("Cancel change widget name via header")
def test_cancel_change_widget_name_via_header(metapix):
    widget = create_any_widget(metapix.dashboard, 'face')
    assert widget.header_text == widget.title

    old_title = widget.header_text
    widget.enter_edit_title_mode()
    widget.set_title("Test title")
    widget.cancel_title(old_title=old_title)
    assert widget.header_text == old_title

    metapix.refresh()
    assert widget.header_text == old_title


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Change widget name via settings")
def test_change_widget_name_via_settings(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type="face")

    widget.open_settings(). \
        set_title("Hello").apply()
    assert metapix.dashboard.widgets_titles == ["Hello"]

    metapix.refresh()
    assert widget.header_text == "Hello"


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Cancel change widget name via header")
def test_cancel_change_widget_name_via_settings(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type="face")
    old_title = widget.title

    widget.open_settings(). \
        set_title("Hello").cancel()
    assert metapix.dashboard.widgets_titles == [old_title]

    metapix.refresh()
    assert widget.header_text == old_title


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Owner (has 1 company) shares the widget for himself")
def test_shared_widget_owner_with_1_company_himself(metapix, sender, another_driver):
    """
    User #1                           User #1
       |           >>> share >>>         |
    Company #1                        Company #1
    """
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="face")
    shared_widget = widget.share(another_driver)

    check_change_timeslice(sender, shared_widget, "face")
    check_autorefresh_works(sender, shared_widget, "face")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/layout-manager/-/issues/70")
@allure.title("Owner shares the widget to ANOTHER user in the same company (both have 1 company)")
def test_shared_widget_user_from_same_company_both_have_1_company(
        metapix, sender, another_driver, client_admin):
    """
    User #1                           User #2
       |           >>> share >>>         |
    Company #1                        Company #1
    """
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="face")
    auth_user_in_browser(another_driver, client_admin)
    shared_widget = widget.share(another_driver)

    check_change_timeslice(sender, shared_widget, "face")
    check_autorefresh_works(sender, shared_widget, "face")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Opening a shared widget by a user from another company is not available")
def test_shared_user_user_from_other_company(
        metapix, another_driver, client_spc, sender):
    """
    User #1                           autotest@metapix.ai
       |           >>> share >>>              |
    Company #1                        Metapix Test
    """
    sender.check_min_objects_count({"person": 1})
    auth_user_in_browser(another_driver, client_spc)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="person")

    shared_widget = widget.share(another_driver)
    # TODO: try another way to check that widget isn't opened
    assert shared_widget.objects_count == 0


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Owner (has 2 companies) shares the widget for himself")
@pytest.mark.usefixtures('second_company')
def test_shared_widget_owner_with_2_companies_himself(metapix, sender, another_driver):
    """
    User #1                           User #1
       |           >>> share >>>         |
    Company #1                        Company #1
    Company #2                        Company #2
    """
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="face")
    shared_widget = widget.share(another_driver)

    check_change_timeslice(sender, shared_widget, "face")
    check_autorefresh_works(sender, shared_widget, "face")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/layout-manager/-/issues/70")
@allure.title("Owner shares the widget to ANOTHER user in the same company (both have 2 companies)")
@pytest.mark.usefixtures('second_company')
def test_shared_widget_user_from_same_company_both_have_2_companies(
        metapix, sender, another_driver, client_admin, second_company_admin):
    """
    User #1                           User #2
       |           >>> share >>>         |
    Company #1                        Company #1
    Company #2                        Company #3
    """
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="face")
    auth_user_in_browser(another_driver, client_admin)
    shared_widget = widget.share(another_driver)

    check_change_timeslice(sender, shared_widget, "face")
    check_autorefresh_works(sender, shared_widget, "face")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("test cancel widget filters")
def test_cancel_widget_filters(metapix, sender):
    sender.check_diff_objects_count_in_cameras("face", "camera-1", "camera-2")
    widget = create_any_chart(metapix.dashboard, 'face')

    settings = widget.open_settings()
    settings.open_camera_picker(). \
        set_filters(cameras=['camera-1']). \
        cancel()

    assert settings.button_filter_by_cameras.value == 'Filtered by: 4 Cameras'
    settings.apply()
    assert widget.objects_count == sender.objects_count("face")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Closing camera/loc filters should discard changes")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1205')
@allure.tag('bug')
def test_closing_filters_does_not_save_camera_state(metapix):
    widget = create_any_widget(metapix.dashboard, 'face')
    widget.set_filters(cameras=['camera-1', 'camera-2'])

    settings = widget.open_settings()
    filter_dialog = settings.open_camera_picker()
    filter_dialog.get_camera('camera-1').unselect()
    filter_dialog.close()
    settings.apply()

    filter_dialog = widget.open_settings(). \
        open_camera_picker()
    with allure.step('Check cameras state has not been changed after closing filter dialog'):
        assert filter_dialog.schema == ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☐', 'camera-4 ☐']


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Check Widget header buttons (edit title mode)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/704')
def test_edit_title_header_icons(metapix):
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_VALUE, 'vehicle')

    widget.enter_edit_title_mode()
    assert widget.header_buttons_schema == ['CONFIRM', 'CANCEL', 'AUTOREFRESH INFO', 'ADJUST', 'MORE']


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Widgets: 'Not empty' checkboxes work for object notes for ({widget_type} + {base})")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/568")
@pytest.mark.usefixtures('teardown_delete_object_notes')
@pytest.mark.parametrize(
    'base, notes_count',
    [('face', 2), ('vehicle', 3)],
    ids=['face', 'vehicle'],
)
@pytest.mark.parametrize(
    "widget_type",
    [consts.WIDGET_BAR_CHART, consts.WIDGET_LIVE_FEED],
    ids=['bar_chart', 'live_feed'],
    # TODO: add more widget types
)
def test_widget_not_empty_checkboxes_object_notes(metapix, sender, base, notes_count, widget_type):
    timeslice = None if widget_type == consts.WIDGET_LIVE_FEED else '2w'
    sender.check_min_objects_count({base: notes_count}, timeslice=timeslice)
    prepare_objects_with_notes(sender, base, notes_count)

    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type=base)
    if widget_type != consts.WIDGET_LIVE_FEED:
        widget.set_timeslice(timeslice)  # TODO: 2w couldn't be enough

    settings = widget.open_settings()
    settings.input_object_note.checkbox.select()
    assert settings.input_object_note.value == "Not empty"
    settings.apply()
    widget.assert_objects_count(notes_count)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/341")
@allure.title("[Legend] Fast clicks in legend cause to chart fail (affect bar/line/pie chart for all types of objects)")
def test_legend_fast_click(sender, metapix):
    sender.check_min_objects_count({gender: 1 for gender in consts.FACE_GENDERS})
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_pie_chart_widget(object_type="face")
    objects_count = widget.objects_count
    for legend_button in widget.legend:
        [legend_button.switch() for _ in range(4)]  # click even times
        try:
            # we should interact with every sector:
            # if bug is reproducible then all sectors exists but one of them is not visible
            widget.assert_objects_count(objects_count)
        except SectorNotInteractableException:
            pytest.fail("metapix-cloud/client/metapix-frontend-app/-/issues/338")


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/370')
@allure.title('Camera filters should not reset after applying filters in widget builder')
def test_camera_does_not_reset_after_applying_filter_in_settings(sender, metapix):
    widget = create_any_widget(metapix.dashboard, 'face')
    widget.set_filters(cameras=['camera-1'])
    widget.open_settings().select_gender('male').apply()
    filters = widget.open_settings(). \
        open_camera_picker()
    assert filters.schema == ['camera-1 ☑', 'camera-2 ☐', 'camera-3 ☐', 'camera-4 ☐']


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/804")
@allure.title("Autorefresh resets if case user leaves dashboard")
@pytest.mark.parametrize("widget_type,sender_kwargs", [
    (consts.WIDGET_BAR_CHART, {}),
])
def test_autorefresh_resets_if_user_leaves_dashboard(metapix, widget_type, sender, sender_kwargs):
    sender.check_min_objects_count({'face': 1})
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type='face'). \
        enable_autorefresh()
    metapix.open_settings()
    sender.send("face")
    sender.wait_autorefresh_time()
    metapix.open_dashboard()

    widget.assert_autorefresh_enabled()
    assert widget.objects_count == sender.objects_count('face', **sender_kwargs)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/446")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/811")
@allure.title("It is possible to set custom timeslice for shared widget")
def test_it_is_possible_to_set_custom_timeslice_for_shared_widget(metapix, another_driver, client):
    auth_user_in_browser(another_driver)
    shared_widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='face').share(another_driver)

    timeslice_page = shared_widget.open_custom_timeslice()
    timeslice_page.range_from.open_calendar().select_day("1")
    timeslice_page.range_to.open_calendar().select_day("1")
    timeslice_page.submit()


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Filtering by empty location shows no objects")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_widget_filter_by_empty_location(metapix, sender):
    # TODO: should we use another widgets/bases?
    check_filter_by_empty_location(metapix, sender, consts.WIDGET_BAR_CHART, 'face')


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/485")
@allure.title("Image quality value must remain good after changing base of widget")
def test_image_quality_remain_good_after_changing_base(metapix):
    builder = metapix.dashboard.open_widget_builder(). \
        choose_widget_type(consts.WIDGET_BAR_LINE_CHART)
    image_quality_val = builder.select_base(consts.BASE_VEHICLE).filter_image_quality.value
    assert image_quality_val == consts.SOURCE_IMG_QUALITY_GOOD


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/452")
@allure.title("Widget settings are saved after the form is closed")
def test_widget_settings_has_not_been_saved_if_closed(metapix):
    # TODO: more settings
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(object_type="face")
    widget.open_settings(). \
        select_gender("male"). \
        cancel()
    assert widget.open_settings().filter_gender.value == "All"


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/460")
@allure.title("Check settings title")
def test_widget_settings_title(metapix):
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_value_widget(object_type="person")
    settings_page = widget.open_settings()
    assert settings_page.header_title == "Widget settings"


@allure.epic("Backend")
@allure.tag("bug")
@allure.link(
    "https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/91")
@allure.title("Set image_quality filter to 'good' for all types of objects")
def test_good_image_quality_filter_by_default(metapix):
    builder = metapix.dashboard.open_widget_builder(). \
        choose_widget_type(consts.WIDGET_LIVE_FEED)
    builder.select_base(consts.BASE_VEHICLE)
    assert builder.filter_image_quality.value == consts.SOURCE_IMG_QUALITY_GOOD


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Filters applied for every timeslice for {object_type}")
@pytest.mark.parametrize(
    'object_type,filters',
    [
        ('face-female', consts.FILTER_FEMALE),
        ('vehicle-type-truck', consts.FILTER_TRUCK),
    ],
    ids=['face', 'vehicle'],
)
def test_chart_filters_applied_for_every_timeslice(metapix, sender, object_type, filters):
    # TODO: more filters
    for timeslice in ('12h', '6h', '1w', '2w'):
        sender.check_diff_objects_count(
            ['face-male', 'face-female', 'vehicle-type-suv', 'vehicle-type-truck'],
            timeslice=timeslice,
        )
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_bar_chart_widget(object_type=object_type)
    widget.open_settings(). \
        set_filters(filters). \
        apply()

    for timeslice in ('6h', '1w', '2w', '12h'):
        widget.set_timeslice(timeslice)
        widget.assert_objects_count(sender.objects_count(object_type, timeslice=timeslice))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/447")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1093")
@allure.title("Shared widget with custom timeslice is empty")
def test_shared_widget_with_custom_timeslice_is_empty(metapix, driver, another_driver, sender):
    sender.check_min_objects_count({"face-male": 1})
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='face')

    widget.open_custom_timeslice().submit()  # submit default date range
    shared_widget = widget.share(another_driver)
    # TODO: problem is possible: unexpected amount of objects for "Custom" timeslice
    shared_widget.assert_objects_count(sender.objects_count('face', timeslice='custom_default'))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/443")
@allure.title("Empty chart widget after setting custom timeslice and page reload")
def test_empty_widget_after_custom_timeslice_and_refresh(metapix, sender):
    sender.check_min_objects_count({"face": 1})
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='face')
    assert widget.objects_count == sender.objects_count("face")
    widget.open_custom_timeslice().submit()
    metapix.refresh()
    # TODO: problem is possible: unexpected amount of objects for "Custom" timeslice
    # TODO: please fix this test
    widget.assert_objects_count(sender.objects_count('face', timeslice='custom_default'))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/124")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/657")
@allure.title("Legend buttons have the same color after changing timeslice, refreshing page, etc")
def test_chart_legend_keep_colors_state(metapix, sender):
    # TODO: add more scenaries
    sender.check_min_objects_count({vehicle: 1 for vehicle in consts.VEHICLE_TYPE_TEMPLATES})
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='vehicle')
    expected_colors = {e.name: e.color for e in widget.legend}
    assert len(expected_colors) >= len(consts.VEHICLE_TYPE_TEMPLATES), "Objects have not arrived"
    assert len(expected_colors) == len(set(expected_colors.values())), \
        "Not all colors are different"

    # colors are same for another time slice
    widget.set_timeslice("1w")
    assert {e.name: e.color for e in widget.legend} == expected_colors

    # colors are same after refresh
    metapix.refresh()
    assert {e.name: e.color for e in widget.legend} == expected_colors


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/382")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/426")
@allure.title("Bar/line chart`s time setting resets when the widget is changed through the settings")
def test_chart_timeslice_resets_if_setting_changed(sender, metapix):
    ''' Check test_chart_timeslice_persists_after_refresh '''
    sender.check_min_objects_count({"face-male": 1, "face-female": 2})
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='face')

    # scenario 1: timeslice 1w
    widget.set_timeslice("1w")
    widget.open_settings().select_gender(consts.GENDER_MALE).apply()
    assert widget.objects_count == sender.objects_count("face", consts.META_MALE, timeslice='1w')
    assert widget.selected_timeslice_value == "1w"

    # scenario 2: custom timeslice
    # TODO: custom timeslice by default - last 12 hours
    widget.open_custom_timeslice().submit()
    widget.open_settings().select_gender(consts.GENDER_FEMALE).apply()
    assert widget.objects_count == sender.objects_count("face", consts.META_FEMALE, timeslice='custom_default')
    assert widget.selected_timeslice_value == "Custom"


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Timeslice state persists after refresh for {base}. (is shared: {is_shared})")
@pytest.mark.parametrize(
    'widget_type,base,is_shared',
    [
        (consts.WIDGET_VALUE, 'face', False),
        (consts.WIDGET_BAR_CHART, 'vehicle', True),
    ],
    ids=['not-shared_value_face', 'shared_bar_chart_vehicle'],
)
def test_chart_timeslice_persists_after_refresh(metapix, sender, widget_type, base, is_shared, another_driver):
    ''' Check test_chart_timeslice_resets_if_setting_changed '''
    sender.send(base, timestamp=time.time() - 60 * 60 * 24 * 10)  # 10 days ago TODO: use Ago
    sender.check_diff_objects_count(['face', 'vehicle'], timeslice='2w')
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type=base)
    if is_shared:
        auth_user_in_browser(another_driver)
        widget = widget.share(another_driver)
    widget.set_timeslice('2w')

    widget.refresh()
    assert widget.selected_timeslice_value == '2w'
    assert widget.objects_count == sender.objects_count(base, timeslice='2w')


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/388")
@allure.title("[FILTERS] Add support of All value in filters")
def test_widget_settings_double_all_entry(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type="person")
    widget_settings = widget.open_settings()
    widget_settings.filter_image_quality.expand()
    options = [o.lower() for o in widget_settings.filter_image_quality.options]
    assert len(options) == len(widget_settings.filter_image_quality.options)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/458")
@allure.title("Disable buttons 'ADD WIDGET' and 'CHANGE WIDGET' while frontend is waiting for a response from backend")
def test_create_several_widgets_by_clicking_create_widget_button(metapix):
    # TODO: extend test. There are more than one possible scenarios
    builder = metapix.dashboard.open_widget_builder(). \
        choose_widget_type(consts.WIDGET_VALUE)
    builder.set_title("Test value widget")
    builder.select_base("face", delay=0.5)
    for _ in range(5):
        try:
            builder.button_ok.click()
            time.sleep(0.1)
        except (ElementClickInterceptedException,
                ElementIsNotClickableException,
                NoElementException,
                StaleElementReferenceException):
            pass
    builder.wait_disappeared()
    assert len(metapix.dashboard.widgets_titles) == 1, \
        "Too many widgets have been created :)"


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/424")
@allure.title("Object's notes, Object's notes in Widget Builder: it is possible to type text")
def test_it_is_possible_to_type_note_and_name(metapix):
    builder = metapix.dashboard.open_widget_builder(). \
        choose_widget_type(consts.WIDGET_LIVE_FEED)
    builder.select_base("vehicle")

    assert builder.set_object_note("note").input_object_note.value == "note"
    assert builder.set_object_name("name").input_object_name.value == "name"


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/846')
@allure.title("Widget name persists after drag and drop the header")
@pytest.mark.parametrize('new_title', ['Test title'])
def test_widget_name_persists_after_drag_and_drop_header(metapix, new_title):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type="face")

    check_is_possible_to_rename_widget(widget, refresh_check=False, new_title=new_title)
    for _ in range(5):
        widget.drag_and_drop(20, 20)
    assert widget.header_text == new_title


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Choose widget type: cancel button works")
def test_cancel_choosing_widget_type(metapix, driver):
    metapix.open_dashboard(). \
        open_widget_builder(). \
        cancel()
    assert is_element_exist(lambda: ChooseWidgetType(driver=driver)) is False


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Widget builder: cancel button works")
def test_widget_builder_cancel(metapix, driver):
    widget_builder = metapix.open_dashboard(). \
        open_widget_builder(). \
        choose_widget_type(consts.WIDGET_VALUE)

    widget_builder.cancel()
    assert is_element_exist(lambda: ChooseWidgetType(driver=driver)) is False
    assert is_element_exist(lambda: WidgetsBuilder(driver=driver)) is False


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Widget builder: 'change type' button works")
def test_widget_builder_change_type(metapix, sender):
    sender.check_min_objects_count(
        {'vehicle-type-sedan': 1, 'vehicle-type-minivan': 1})
    widget_builder = metapix.open_dashboard(). \
        open_widget_builder(). \
        choose_widget_type(consts.WIDGET_VALUE)

    dialog_widget_type = widget_builder.change_type()
    assert dialog_widget_type.title == 'Choose widget type'

    widget = dialog_widget_type. \
        choose_widget_type(consts.WIDGET_PIE_CHART). \
        create_pie_chart_widget('vehicle')
    with allure.step('Check it is really pie chart'):
        assert len(widget.sectors) > 1


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("It is possible to move widget to another cell with drag and drop")
def test_widget_drag_and_drop_to_another_cell(metapix):
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_value_widget(object_type="face")
    initial_box = widget.box
    widget.drag_and_drop(consts.MIN_OFFSET_TO_MOVE_WIDGET, 0)
    assert widget.box.x0 >= initial_box.x0  # check widget has been moved to right

    widget.drag_and_drop(-consts.MIN_OFFSET_TO_MOVE_WIDGET, 0)
    assert widget.box == initial_box


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("It is possible to swap two widgets with drag and drop")
def test_widget_drag_and_drop_swap_widgets(metapix):
    # TODO: do not change timeslice during creating widgets
    first_widget = metapix.dashboard. \
        open_widget_builder(). \
        create_value_widget(object_type="face")
    second_widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_value_widget(object_type="vehicle")

    # normalize: first widget should be to the left (above) of second widget
    if first_widget.box.x0 > second_widget.box.x1:
        first_widget, second_widget = second_widget, first_widget
    if first_widget.box.y0 > second_widget.box.y1:
        first_widget, second_widget = second_widget, first_widget

    # scroll to the top of dashboard to make the first widget header visible
    metapix.scroll_to_element(metapix.layout.current_layout_button)
    # move the first widget right (down) / swap widgets
    first_widget.drag_and_drop(
        second_widget.box.x0 - first_widget.box.x0,
        second_widget.box.y0 - first_widget.box.y0,
    )

    # check that the first widget is below / on the right
    assert first_widget.box.x0 > second_widget.box.x1 \
           or first_widget.box.y0 > second_widget.box.y1


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("In custom timeslice start date has to be 24 earlier then end date")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1121')
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1093")
def test_widget_custom_timeslice_start_and_end_dates_are_not_equal(metapix):
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_value_widget(object_type="face")
    custom_timeslice = widget.open_custom_timeslice()
    assert custom_timeslice.range_from.to_datetime() + timedelta(hours=12) == \
        custom_timeslice.range_to.to_datetime()


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Charts: custom timeslice works")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1130')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1161')
@pytest.mark.parametrize(
    'timeslice,detalization', [
        (Ago('-3h'), consts.HOUR_SECONDS // 2),
    ],
    ids=['3h'],
)
@pytest.mark.parametrize('widget_type', [consts.WIDGET_BAR_CHART])
def test_chart_custom_timeslice(metapix, sender, widget_type, timeslice, detalization):
    fill_intervals_with_objects(sender, 'vehicle', timeslice, detalization)
    widget = metapix.dashboard.open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type='vehicle')
    with allure.step('Check there are no errors after submitting custom timeslice'):
        widget.set_custom_timeslice(date_from=timeslice.dt)
        widget.assert_objects_count(sender.objects_count('vehicle', date_from=timeslice.dt))


@allure.epic('Frontend')
@allure.tag('bug')
@allure.suite('Widgets')
@allure.title('It should be possible to close the window if no camera is selected')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1160')
def test_widget_cannot_close_filter_dialog_if_no_camera_is_selected(metapix):
    widget = create_any_widget(metapix.dashboard)
    filter_dialog = widget.open_settings(). \
        open_camera_picker(). \
        clear_all()
    filter_dialog.close()


@allure.epic('Frontend')
@allure.tag('bug')
@allure.suite('Widgets')
@allure.title('Special characters in "cluster name" and "object notes" are properly encoded in GET request')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1151')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1438')
@pytest.mark.parametrize('widget_type', [consts.WIDGET_PIE_CHART, consts.WIDGET_LIVE_FEED, consts.WIDGET_BAR_CHART])
def test_widget_special_chars_in_settings_are_properly_encoded_in_url(metapix, sender, widget_type):
    def fix_state(state):
        if widget_type in consts.WIDGET_ALL_CHARTS:
            del state['legend']
            if widget_type == consts.WIDGET_VALUE:
                del state['counter']
            else:
                del state['chart_state']
        if widget_type == consts.WIDGET_LIVE_FEED:
            del state['thumbs']
        return state

    sender.check_min_objects_count({'face': 1})
    widget = create_widget_api(metapix.dashboard, widget_type, 'face')
    expected_state = fix_state(widget.state)
    widget.open_settings(). \
        set_filters({consts.FILTER_OBJECTS_NAME: 'Object #1', consts.FILTER_OBJECTS_NOTES: 'Note #2'}). \
        apply()
    assert fix_state(widget.state) == expected_state
    # TODO: find out the cause of this check
    # with pytest.raises(NoSectorsException):  # FYI: applicable only for PIE CHART
    #     widget.objects_count


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.tag('bug')
@allure.title('All cameras are marked as selected by default')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1135')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_all_cameras_and_locs_are_selected_by_default(metapix, client):
    create_location_schema_api(client, {
        "Garden": ['camera-1'],
        "Enterance": [],
    })
    widget = create_any_widget(metapix.dashboard)
    filter_dialog = widget.open_settings(). \
        open_camera_picker()
    for entity in filter_dialog.root_locs + filter_dialog.cameras:
        assert entity.is_checked()


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.tag('bug')
@allure.title('Filters satete remains unchanged after autorefresh request')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1204')
def test_chart_filters_unchanged_after_autorefresh(metapix, sender):
    sender.check_diff_objects_count({'face-female': 1, 'face-male': 1})
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, 'face')
    widget.open_settings(). \
        set_filters(consts.FILTER_FEMALE). \
        apply()
    widget.enable_autorefresh()
    expected_state = widget.state
    sender.wait_autorefresh_time()
    assert are_dicts_equal(widget.state, expected_state)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Changing timezone affects autorefresh timestamp')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1488')
@pytest.mark.usefixtures("teardown_restore_timezone")
def test_chart_timezone_in_autorefresh_timestamp(metapix, sender):
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, 'face')
    widget.enable_autorefresh()
    date_before = parse_widget_updated_date(widget)
    change_timezone(sender.client, 'Europe/Helsinki')
    metapix.refresh()
    assert timedelta_hours(parse_widget_updated_date(widget) - date_before) in (9, 10)


def check_add_widget_button_below_other_widgets(button_add, widgets):
    with allure.step(f'Check that "Add widget" button below {len(widgets)} widgets'):
        for widget in widgets:
            assert button_add.location['y'] > widget.box.y1


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('After adding a widget "New widget" button appears below')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1222')
def test_add_widget_button_appears_below(metapix):
    widgets = []
    for widget_type in consts.WIDGET_ALL_TYPES:
        with allure.step(f'Create {widget_type} widget and check position of "Add widget" button'):
            widgets.append(
                metapix.dashboard.open_widget_builder().
                create_widget(widget_type=widget_type, object_type="face")
            )
            check_add_widget_button_below_other_widgets(
                metapix.dashboard.button_add_widget,
                widgets,
            )


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.tag('bug')
@allure.title('The Cluster name should not change in widget settings')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1313')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1355')
@pytest.mark.parametrize('cluster_name', ['Name with spaces'])
@pytest.mark.parametrize('base', ['face'])
def test_cluster_name_with_special_chars_in_settings(metapix, cluster_name, base):
    widget = create_any_chart(metapix.dashboard, base)
    widget.open_settings(). \
        set_filters({consts.FILTER_OBJECTS_NAME: cluster_name}). \
        apply()
    widget.set_timeslice('1h')  # it is possible to reproduce the bug only with this step
    settings = widget.open_settings()
    assert settings.input_object_name.value == cluster_name


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.tag('bug')
@allure.title('The app should not crash during typing % symbol in cluster name field')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1377')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1420')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/414')
@pytest.mark.parametrize('cluster_name', ['Percent %'])
@pytest.mark.parametrize('base', ['face'])
def test_percent_symbol_in_cluster_name_field(metapix, cluster_name, base):
    widget = create_any_chart(metapix.dashboard, base)
    widget.open_settings(). \
        set_filters({consts.FILTER_OBJECTS_NAME: cluster_name}). \
        apply()
    assert metapix.dashboard.widgets_titles == [widget.title]   # check app works

    settings = widget.open_settings()
    assert settings.title == 'Widget settings'  # check app works


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Widget name should be changed in the hint automatically')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1378')
@pytest.mark.parametrize('new_title', ['hello'])
def test_renamed_widget_title_hint(metapix, new_title):
    def get_widget_title_tooltip(widget: NotSharedWidget) -> str:
        with allure.step(f'Getting tooltip for header for {widget}'):
            log.info(f'Getting tooltip for header for {widget}')
            widget._action_chains.move_to_element(widget.header_title).perform()
            element = widget.get_object(XPathType("//div[contains(@class, 'MuiTooltip') and @role='tooltip']"))
            return element.text

    widget = create_any_widget(metapix.dashboard)

    with allure.step('Check widget title tooltip right after applying a new title via settings'):
        widget.open_settings(). \
            set_title(new_title).apply()
        assert get_widget_title_tooltip(widget) == new_title

    with allure.step('Check widget title tooltip after refreshing the page'):
        widget.refresh()
        assert get_widget_title_tooltip(widget) == new_title


def prepare_affect_test(widget, check_method: Callable, sender: ImageSender, base: BaseType) -> Generator:
    sender_kwargs = {}
    if widget.type == consts.WIDGET_LIVE_FEED:
        sender_kwargs['timeslice'] = None

    if widget.type == consts.WIDGET_VALUE and \
       check_method == check_original_widget_and_shared_does_not_affect_each_other_autorefresh:
        pytest.skip('Value widget does not have autorefresh')

    if widget.type in (consts.WIDGET_VALUE, consts.WIDGET_LIVE_FEED) and \
       check_method == check_original_widget_and_shared_does_not_affect_each_other_legend:
        pytest.skip(f'{widget.type} does not have legend')

    if widget.type == consts.WIDGET_LIVE_FEED and \
       check_method == check_original_widget_and_shared_does_not_affect_each_other_timeslice:
        pytest.skip('Live feed does not have timeslice')

    if widget.type not in (consts.WIDGET_VALUE, consts.WIDGET_LIVE_FEED) \
       and check_method == check_original_widget_and_shared_does_not_affect_each_other_autorefresh:
        widget.enable_autorefresh()

    return run_test(check_method(sender=sender, base=base, **sender_kwargs))


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Original widget does`t affect shared widget. Base={base}')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'check_method',
    [
        check_original_widget_and_shared_does_not_affect_each_other_timeslice,
        check_original_widget_and_shared_does_not_affect_each_other_camera,
        check_original_widget_and_shared_does_not_affect_each_other_location,
        check_original_widget_and_shared_does_not_affect_each_other_changing_base,
        check_original_widget_and_shared_does_not_affect_each_other_autorefresh,
        check_original_widget_and_shared_does_not_affect_each_other_legend,
    ],
    ids=['timeslice', 'cameras', 'locs', 'base', 'autorefresh', 'legend'],
)
def test_original_widget_does_not_affect_shared(
        metapix: RootPage,
        another_driver: CustomWebDriver,
        sender: ImageSender,
        base: BaseType,
        check_method: Callable):  # TODO: clarify type
    auth_user_in_browser(another_driver)
    original_widget = create_any_widget(metapix.dashboard, base)
    test = prepare_affect_test(original_widget, check_method, sender, base)

    shared_widget = original_widget.share(another_driver)
    send_value_to_test(test, original_widget, shared_widget)  # the first widget is widget to change


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Shared widget does`t affect original widget. Base={base}')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['vehicle'])
@pytest.mark.parametrize(
    'check_method',
    [
        check_original_widget_and_shared_does_not_affect_each_other_timeslice,
        check_original_widget_and_shared_does_not_affect_each_other_autorefresh,
        check_original_widget_and_shared_does_not_affect_each_other_legend,
    ],
    ids=['timeslice', 'autorefresh', 'legend'],
)
def test_shared_widget_does_not_affect_original(
        metapix: RootPage,
        another_driver: CustomWebDriver,
        sender: ImageSender,
        base: BaseType,
        check_method: Callable):  # TODO: clarify type
    auth_user_in_browser(another_driver)
    original_widget = create_any_widget(metapix.dashboard, base)
    test = prepare_affect_test(original_widget, check_method, sender, base)

    shared_widget = original_widget.share(another_driver)
    send_value_to_test(test, shared_widget, original_widget)  # the first widget is widget to change


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Original widget does`t affect widget on shared layout. Base={base}')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'check_method',
    [
        check_original_widget_and_shared_does_not_affect_each_other_timeslice,
        check_original_widget_and_shared_does_not_affect_each_other_camera,
        check_original_widget_and_shared_does_not_affect_each_other_location,
        check_original_widget_and_shared_does_not_affect_each_other_changing_base,
        check_original_widget_and_shared_does_not_affect_each_other_autorefresh,
        check_original_widget_and_shared_does_not_affect_each_other_legend,
    ],
    ids=['timeslice', 'cameras', 'locs', 'base', 'autorefresh', 'legend'],
)
def test_original_widget_does_not_affect_widget_on_shared_layout(
        metapix: RootPage,
        another_driver: CustomWebDriver,
        sender: ImageSender,
        base: BaseType,
        check_method: Callable):  # TODO: clarify type
    auth_user_in_browser(another_driver)
    original_widget = create_any_widget(metapix.dashboard, base)
    test = prepare_affect_test(original_widget, check_method, sender, base)

    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=original_widget)
    send_value_to_test(test, original_widget, shared_widget)  # the first widget is widget to change


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Widget on shared layout does`t affect original widget. Base={base}')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'check_method',
    [
        check_original_widget_and_shared_does_not_affect_each_other_timeslice,
        check_original_widget_and_shared_does_not_affect_each_other_camera,
        check_original_widget_and_shared_does_not_affect_each_other_location,
        check_original_widget_and_shared_does_not_affect_each_other_changing_base,
        check_original_widget_and_shared_does_not_affect_each_other_autorefresh,
        check_original_widget_and_shared_does_not_affect_each_other_legend,
    ],
    ids=['timeslice', 'cameras', 'locs', 'base', 'autorefresh', 'legend'],
)
def test_widget_on_shared_layout_does_not_affect_original_widget(
        metapix: RootPage,
        another_driver: CustomWebDriver,
        sender: ImageSender,
        base: BaseType,
        check_method: Callable):  # TODO: clarify type
    auth_user_in_browser(another_driver)
    original_widget = create_any_widget(metapix.dashboard, base)
    test = prepare_affect_test(original_widget, check_method, sender, base)

    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=original_widget)
    send_value_to_test(test, shared_widget, original_widget)  # the first widget is widget to change


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Widget menu is visible and available in case a user has stretched the widget to maximum size')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1450')
def test_widget_resize_max_width(metapix: RootPage):
    def resize_to_max_width(widget: NotSharedWidget):
        dx = widget.get_available_space()[0] + 30
        while True:
            log.info(f'Try {dx=}')
            try:
                widget.resize(dx=dx)
            except MoveTargetOutOfBoundsException:
                dx -= 5
            else:
                break
        assert widget.get_available_space()[0] < 20

    widget = create_any_widget(metapix.dashboard)
    resize_to_max_width(widget)

    with allure.step('Check widget settings is available'):
        widget.open_settings()


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Widgets should take into account new camera added to locatoin')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/583')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_add_camera_to_location_used_by_widget(
        metapix: RootPage, client: ApiClient, base: BaseType):
    create_location_schema_api(
        client,
        {
            'loc': ['camera-1', 'camera-2'],
        }
    )
    widget = create_any_chart(metapix.dashboard, base)
    widget.set_filters(locations=['loc'])
    bind_camera_to_location_by_name(client, 'camera-3', 'loc')
    camera_picker = widget.open_settings(). \
        open_camera_picker(). \
        expand_all_locations()
    assert camera_picker.schema == [{'▲ loc ☑': ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☑']}, 'camera-4 ☐']
    raise NotImplementedError('TODO: consider solution')


@allure.epic('Frontend')
@allure.tag('bug')
@allure.suite('Widgets')
@allure.title('Check camera picker state after clicking "Clear All" button')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1548')
def test_widget_camera_picker_state_after_clicking_clear_all_button(metapix: RootPage):
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_VALUE, 'face')
    camera_picker = widget.open_settings(). \
        open_camera_picker()
    camera_picker.clear_all()
    time.sleep(15)
    assert camera_picker.schema == ['camera-1 ☐', 'camera-2 ☐', 'camera-3 ☐', 'camera-4 ☐']
