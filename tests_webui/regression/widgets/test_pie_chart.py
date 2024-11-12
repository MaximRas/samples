import logging

import pytest
import allure

import consts
from tools import run_test
from tools import send_value_to_test
from tools.users import auth_user_in_browser

from pages.base_page import is_element_exist
from tests_webui.regression.widgets import check_change_base
from tests_webui.regression.widgets import check_filter_by_camera
from tests_webui.regression.widgets import check_filter_by_locations
from tests_webui.regression.widgets import check_hide_show_legend
from tests_webui.regression.widgets import check_hide_show_timeslice
from tests_webui.regression.widgets import check_widget_age_filter
from tests_webui.regression.widgets import check_widget_autorefresh
from tests_webui.regression.widgets import check_widget_settings_default_filter_values
from tests_webui.regression.widgets import check_widget_image_quality
from tests_webui.regression.widgets import check_widget_cluster_name
from tests_webui.regression.widgets import check_widget_object_notes
from tests_webui.regression.widgets import check_widget_license_plate
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state
from tests_webui.regression.widgets import check_widget_looks_same_after_changing_base
from tests_webui.regression.widgets import check_widget_timestamp_in_autorefresh_button
from tests_webui.regression.widgets import check_change_timeslice
from tests_webui.regression.widgets import check_not_empty_checkbox_license_plate

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Shared Pie chart widget keeps location state")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_location_state_pie_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_pie_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_location_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Shared Pie chart widget keeps camera state")
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_camera_state_pie_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_pie_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_camera_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Enable autorefresh and check that object count has risen for {object_type}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/156")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-minivan"])
def test_pie_chart_autorefresh(sender, metapix, object_type):
    check_widget_autorefresh(consts.WIDGET_PIE_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Filtering by cameras (pie chart / {object_type})")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/156")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-wagon"])
def test_pie_chart_filter_by_camera(sender, metapix, object_type):
    check_filter_by_camera(consts.WIDGET_PIE_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Filtering by locations (pie chart) for {base}")
@pytest.mark.parametrize("base", ["face", "vehicle"])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_pie_chart_filter_by_location(sender, metapix, client, base):
    check_filter_by_locations(consts.WIDGET_PIE_CHART, client, metapix, base, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Widget looks the same after changing base and back")
@pytest.mark.parametrize("initial_base, another_base", [("face", "vehicle"), ("vehicle", "face")])
def test_widget_looks_same_after_changing_base_pie(sender, metapix, initial_base, another_base):
    check_widget_looks_same_after_changing_base(sender, another_base, consts.WIDGET_PIE_CHART, initial_base, metapix)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Objects arrive if Settings->Base has been changed")
def test_pie_chart_objects_arrive_after_base_was_changed(sender, metapix):
    check_change_base(sender, metapix, consts.WIDGET_PIE_CHART, ["face", "vehicle"], enable_autorefresh=True)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check Pie chart header buttons")
def test_pie_chart_header_icons(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_pie_chart_widget(object_type="vehicle")

    assert widget.header_buttons_schema == ["AUTOREFRESH", "ADJUST", "MORE"]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check Pie chart settings filters")
def test_pie_char_settings_filters(metapix):
    check_widget_settings_default_filter_values(
        metapix.dashboard.open_widget_builder().
        create_pie_chart_widget(object_type="vehicle"),
        is_pie_chart=True,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check hide/show lengend works (adjust menu)")
@pytest.mark.parametrize('base', ['vehicle'])
def test_pie_chart_hide_show_legend(metapix, sender, base):
    sender.check_min_objects_count({
        'face-male': 1,
        'face-female': 1,
        'vehicle-type-sedan': 1,
        'vehicle-type-truck': 1,
    })
    check_hide_show_legend(
        metapix.dashboard.
        open_widget_builder().
        create_pie_chart_widget(object_type=base)
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check hide/show timeslice works (adjust menu)")
@pytest.mark.parametrize('base', ['vehicle'])
def test_pie_chart_hide_show_timeslice(metapix, sender, base):
    check_hide_show_timeslice(
        sender,
        metapix.dashboard.
        open_widget_builder().
        create_pie_chart_widget(object_type=base),
        base,
        change_detalization=False,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check age filter for pie chart")
def test_pie_chart_age_filter(metapix, sender):
    check_widget_age_filter(metapix, sender, consts.WIDGET_PIE_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check image quality filter in pie chart builder and settings")
@pytest.mark.parametrize("base", ['face', 'vehicle'])
def test_pie_chart_img_quality(metapix, sender, base):
    check_widget_image_quality(metapix, sender, base, consts.WIDGET_PIE_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check 'cluster name' filter in pie chart builder and settings")
@pytest.mark.parametrize(
    'templates',
    [
        pytest.param(('face-female', 'face-male'), marks=pytest.mark.clusterization_faces),
        ('vehicle-type-truck', 'vehicle-type-suv'),
    ],
    ids=['face', 'vehicle'],
)
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_pie_chart_cluster_name(metapix, sender, templates):
    check_widget_cluster_name(metapix, sender, consts.WIDGET_PIE_CHART, templates)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check 'object notes' filter in pie chart builder and settings")
@pytest.mark.parametrize('base', ['vehicle'])
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_pie_chart_object_notes(metapix, sender, base):
    check_widget_object_notes(metapix, sender, consts.WIDGET_PIE_CHART, base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check 'license plate' filter in pie chart builder and settings")
def test_pie_chart_license_plate(metapix, sender):
    check_widget_license_plate(metapix, sender, consts.WIDGET_PIE_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Pie charts")
@allure.title("Check pie chart changing timeslice works")
def test_pie_chart_changing_timeslice(metapix, sender):
    widget = metapix.dashboard.open_widget_builder(). \
        create_pie_chart_widget(object_type='vehicle')
    check_change_timeslice(sender, widget, 'vehicle', do_teardown=False)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Pie charts')
@allure.title('Autorefresh button contains additional information about autorefresh')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
def test_pie_chart_timestamp_in_autorefresh_button(metapix, sender):
    check_widget_timestamp_in_autorefresh_button(
        metapix,
        metapix.dashboard.open_widget_builder().
        create_pie_chart_widget(object_type='face'),
        sender,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story('Pie charts')
@allure.title("Check that Pie Chart has no detalization field")
def test_pie_chart_has_no_detalization_field(metapix):
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_widget(widget_type=consts.WIDGET_PIE_CHART, object_type="vehicle")

    assert is_element_exist(lambda: widget.button_detalization) is False


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Pie charts')
@allure.title('Widgets: "Not empty" checkboxes work for license plate for pie charts')
def test_widget_not_empty_checkbox_license_plate_pie_chart(metapix, sender):
    check_not_empty_checkbox_license_plate(metapix, sender, consts.WIDGET_PIE_CHART, {"meta": consts.META_LIC_PLATE_ANY})
