import logging

import pytest
import allure

import consts
from tools import run_test
from tools import send_value_to_test
from tools.users import auth_user_in_browser

from tests_webui.regression.widgets import check_widget_age_filter
from tests_webui.regression.widgets import check_hide_show_timeslice
from tests_webui.regression.widgets import check_hide_show_legend
from tests_webui.regression.widgets import check_filter_by_camera
from tests_webui.regression.widgets import check_widget_autorefresh
from tests_webui.regression.widgets import check_filter_by_locations
from tests_webui.regression.widgets import check_widget_cluster_name
from tests_webui.regression.widgets import check_widget_object_notes
from tests_webui.regression.widgets import check_widget_license_plate
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state
from tests_webui.regression.widgets import check_widget_looks_same_after_changing_base
from tests_webui.regression.widgets import check_change_base
from tests_webui.regression.widgets import check_widget_image_quality
from tests_webui.regression.widgets import check_widget_settings_default_filter_values
from tests_webui.regression.widgets import check_widget_timestamp_in_autorefresh_button
from tests_webui.regression.widgets import check_timeslice_detalization

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Shared Line chart widget keeps location state")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_location_state_line_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_line_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_location_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Shared Line chart widget keeps camera state")
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_camera_state_line_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_line_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_camera_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Enable autorefresh and check that object count has risen for {object_type}")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-minivan"])
def test_line_chart_autorefresh(sender, metapix, object_type):
    check_widget_autorefresh(consts.WIDGET_LINE_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Filtering by cameras for {object_type}")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-wagon"])
def test_line_chart_filter_by_camera(sender, metapix, object_type):
    check_filter_by_camera(consts.WIDGET_LINE_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Filtering by locations for (line chart) for {base}")
@pytest.mark.parametrize("base", ["vehicle", "face"])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_line_chart_filter_by_location(sender, metapix, client, base):
    check_filter_by_locations(consts.WIDGET_LINE_CHART, client, metapix, base, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Widget looks the same after changing base and back for {initial_base} -> {another_base}")
@pytest.mark.parametrize("initial_base, another_base", [("face", "vehicle"), ("vehicle", "face")])
def test_widget_looks_same_after_changing_base_line(sender, metapix, initial_base, another_base):
    check_widget_looks_same_after_changing_base(sender, another_base, consts.WIDGET_LINE_CHART, initial_base, metapix)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Objects arrive if Settings->Base has been changed")
def test_line_chart_objects_arrive_after_base_was_changed(sender, metapix):
    check_change_base(sender, metapix, consts.WIDGET_LINE_CHART, ["face", "vehicle", "person"], enable_autorefresh=True)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check objects count for Settings -> Source image quality (Good/Bad/All) for {base}")
@pytest.mark.parametrize("base", [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON])
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/173")
def test_line_chart_img_quality(metapix, sender, base):
    check_widget_image_quality(metapix, sender, base, consts.WIDGET_LINE_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check Line chart header buttons")
def test_line_chart_header_icons(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_line_chart_widget(object_type="vehicle")

    assert widget.header_buttons_schema == ["AUTOREFRESH", "BAR CHART", "LINE CHART", "ADJUST", "MORE"]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check Line chart settings filters")
def test_line_char_settings_filters(metapix):
    check_widget_settings_default_filter_values(
        metapix.dashboard.open_widget_builder().
        create_line_chart_widget(object_type="vehicle")
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check hide/show lengend works (adjust menu)")
@pytest.mark.parametrize('base', ['face'])
def test_line_chart_hide_show_legend(metapix, sender, base):
    sender.check_min_objects_count({
        'face-male': 1,
        'face-female': 1,
        'vehicle-type-sedan': 1,
        'vehicle-type-truck': 1,
    })
    check_hide_show_legend(
        metapix.dashboard.
        open_widget_builder().
        create_line_chart_widget(object_type=base)
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check hide/show timeslice works (adjust menu)")
@pytest.mark.parametrize('base', ['face'])
def test_line_chart_hide_show_timeslice(metapix, sender, base):
    check_hide_show_timeslice(
        sender,
        metapix.dashboard.
        open_widget_builder().
        create_line_chart_widget(object_type=base),
        base,
        change_detalization=True,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check age filter for line chart")
def test_line_chart_age_filter(metapix, sender):
    check_widget_age_filter(metapix, sender, consts.WIDGET_LINE_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check 'cluster name' filter in line chart builder and settings")
@pytest.mark.parametrize(
    'templates',
    [
        pytest.param(('face-male', 'face-female'), marks=pytest.mark.clusterization_faces),
        ('vehicle-type-truck', 'vehicle-type-suv'),
    ],
    ids=['face', 'vehicle'],
)
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_line_chart_cluster_name(metapix, sender, templates):
    check_widget_cluster_name(metapix, sender, consts.WIDGET_LINE_CHART, templates)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check 'object notes' filter in line chart builder and settings")
@pytest.mark.parametrize('base', ['person'])
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_line_chart_object_notes(metapix, sender, base):
    check_widget_object_notes(metapix, sender, consts.WIDGET_LINE_CHART, base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Line charts")
@allure.title("Check 'license plate' filter in line chart builder and settings")
def test_line_chart_license_plate(metapix, sender):
    check_widget_license_plate(metapix, sender, consts.WIDGET_LINE_CHART)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Line charts')
@allure.title('Autorefresh button contains additional information about autorefresh')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
def test_line_chart_timestamp_in_autorefresh_button(metapix, sender):
    check_widget_timestamp_in_autorefresh_button(
        metapix,
        metapix.dashboard.open_widget_builder().
        create_line_chart_widget(object_type='face'),
        sender,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story('Line charts')
@allure.title("Check timeslice detalization for line chart")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/411')
def test_line_chart_timeslice_detalization(metapix, sender):
    check_timeslice_detalization(
        metapix.dashboard.open_widget_builder().
        create_line_chart_widget(object_type='vehicle'),
        sender,
    )
