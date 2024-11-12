import allure
import pytest

import consts
from tools import run_test
from tools import send_value_to_test
from tools import parse_object_type
from tools.users import auth_user_in_browser
from tools.steps import create_widget_api

from pages.base_page import is_element_exist

from tests_webui.regression import check_autorefresh_delta
from tests_webui.regression.widgets import check_change_base
from tests_webui.regression.widgets import check_change_timeslice
from tests_webui.regression.widgets import check_filter_by_camera
from tests_webui.regression.widgets import check_filter_by_locations
from tests_webui.regression.widgets import check_hide_show_timeslice
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state
from tests_webui.regression.widgets import check_widget_age_filter
from tests_webui.regression.widgets import check_widget_cluster_name
from tests_webui.regression.widgets import check_widget_image_quality
from tests_webui.regression.widgets import check_widget_license_plate
from tests_webui.regression.widgets import check_widget_object_notes
from tests_webui.regression.widgets import check_widget_settings_default_filter_values
from tests_webui.regression.widgets import check_not_empty_checkbox_license_plate

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Shared value widget keeps location state")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_location_state_value_widget(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_location_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Shared value widget keeps camera state")
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_camera_state_value_widget(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_camera_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("It should be possible to modify Faces Value widget using Widget Builder")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/611")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/621")
@pytest.mark.parametrize(
    "object_type1, filters1, object_type2, filters2",
    [
        ("face-male", consts.FILTER_MALE, "face-female", consts.FILTER_FEMALE),
        ("vehicle-type-sedan", consts.FILTER_SEDAN, "vehicle-type-truck", consts.FILTER_TRUCK),
    ],
    ids=['face', 'vehicle'],
)
def test_value_widget_modify_via_widget_builder(sender, metapix,
                                                object_type1, filters1,
                                                object_type2, filters2):
    base = parse_object_type(object_type1)[0]
    sender.check_diff_objects_count([object_type1, object_type2])
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type=base)

    widget.open_settings().set_filters(filters1).apply()
    widget.assert_objects_count(sender.objects_count(object_type1))

    widget.open_settings().set_filters(filters2).apply()
    widget.assert_objects_count(sender.objects_count(object_type2))

    # Objects of correct type arrive
    sender.send(object_type1)
    sender.send(object_type2)
    sender.wait_autorefresh_time()
    widget.assert_objects_count(sender.objects_count(object_type2))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Value widget changes value when objects arrive for {base}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/611")
@pytest.mark.parametrize("base", ["face", "vehicle", "person"])
def test_value_widget_objects_arrive(sender, metapix, base):
    sender.check_min_objects_count({base: 1})
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type=base)
    assert widget.objects_count == sender.objects_count(base)

    sender.send(base)
    sender.wait_autorefresh_time()
    assert widget.objects_count == sender.objects_count(base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Objects arrive if Settings->Base has been changed")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/611")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/621")
def test_value_objects_arrive_after_base_was_changed(sender, metapix):
    check_change_base(sender, metapix, consts.WIDGET_VALUE, ["face", "vehicle", "person"])


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Filtering by cameras (value widget)")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/629")
def test_value_filter_by_camera(sender, metapix):
    check_filter_by_camera(consts.WIDGET_VALUE, metapix, "vehicle-type-sedan", sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Filtering by locations (value widget)")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/629")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_value_filter_by_location(sender, metapix, client):
    check_filter_by_locations(consts.WIDGET_VALUE, client, metapix, "face", sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check that Value Widget has no detalization field")
def test_value_widget_has_no_detalization_field(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_widget(widget_type=consts.WIDGET_VALUE, object_type="vehicle")

    assert is_element_exist(lambda: widget.button_detalization) is False


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check objects count for  Settings -> Source image quality (Good/Bad/All)")
@pytest.mark.parametrize("base", [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON])
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/173")
def test_value_img_quality(metapix, sender, base):
    check_widget_image_quality(metapix, sender, base, consts.WIDGET_VALUE)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check value widget header buttons")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/122")
def test_value_header_icons(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_widget(widget_type=consts.WIDGET_VALUE, object_type="vehicle")

    assert widget.header_buttons_schema == ["AUTOREFRESH INFO", "ADJUST", "MORE"]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check value chart settings filters")
def test_value_widget_settings_filters(metapix):
    check_widget_settings_default_filter_values(
        metapix.dashboard.
        open_widget_builder().
        create_value_widget(object_type="vehicle")
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check hide/show timeslice works (adjust menu)")
@pytest.mark.parametrize('base', ['person'])
def test_value_widet_hide_show_timeslice(metapix, sender, base):
    check_hide_show_timeslice(
        sender,
        create_widget_api(metapix.dashboard, consts.WIDGET_VALUE, base),
        base,
        change_detalization=False,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check age filter for value widget")
def test_value_widget_age_filter(metapix, sender):
    check_widget_age_filter(metapix, sender, consts.WIDGET_VALUE)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check 'cluster name' filter in value widget builder and settings for {templates}")
@pytest.mark.parametrize(
    'templates',
    [
        pytest.param(('face-male', 'face-female'), marks=pytest.mark.clusterization_faces),
        ('vehicle-type-truck', 'vehicle-type-suv'),
    ],
    ids=['face', 'vehicle'],
)
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_value_widget_cluster_name(metapix, sender, templates):
    check_widget_cluster_name(metapix, sender, consts.WIDGET_VALUE, templates)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check 'object notes' filter in value widget builder and settings")
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_value_widget_object_notes(metapix, sender, base):
    check_widget_object_notes(metapix, sender, consts.WIDGET_VALUE, base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check 'license plate' filter in value widget builder and settings")
def test_value_widget_license_plate(metapix, sender):
    check_widget_license_plate(metapix, sender, consts.WIDGET_VALUE)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Value")
@allure.title("Check value widget counter style")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1149')
def test_value_widget_counter_style(metapix, sender):
    def _get_area(size):
        return size['width'] * size['height']

    def get_percentage_of_counter(widget):
        return _get_area(widget.text_element.size) / _get_area(widget.root.size)

    sender.check_min_objects_count({'face': 1})
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type='face')

    assert 0.1 <= get_percentage_of_counter(widget) <= 0.8


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Value')
@allure.title('Autorefresh button contains additional information about autorefresh')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
def test_value_widget_autorefresh_timestamp(metapix, sender):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type='face')

    check_autorefresh_delta(widget, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story('Value')
@allure.title("Check value widget changing timeslice works")
def test_value_widget_changing_timeslice(metapix, sender):
    widget = metapix.dashboard.open_widget_builder(). \
        create_value_widget(object_type='vehicle')
    check_change_timeslice(sender, widget, 'vehicle', do_teardown=False)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Value')
@allure.title('Widgets: "Not empty" checkboxes work for license plate for value widget')
def test_widget_not_empty_checkbox_license_plate_value(metapix, sender):
    check_not_empty_checkbox_license_plate(metapix, sender, consts.WIDGET_VALUE, {"meta": consts.META_LIC_PLATE_ANY})
