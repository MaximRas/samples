import logging

import allure
import pytest

import consts
from tools import parse_object_type
from tools import run_test
from tools import send_value_to_test
from tools.image_sender import ImageSender
from tools.objects import get_object
from tools.steps import check_filtering_with_empty_location
from tools.steps import create_location_schema_api
from tools.steps import create_widget_api
from tools.steps import get_hover_tooltip
from tools.types import BaseType
from tools.users import auth_user_in_browser

from pages.base_page import NoElementException
from pages.object_thumbnail import expected_meta_thumbnail
from pages.root import RootPage

from tests_webui.regression import check_card_meta
from tests_webui.regression import check_thumbnail_meta_tooltips
from tests_webui.regression import check_zoom
from tests_webui.regression import parse_widget_updated_date
from tests_webui.regression.widgets import check_change_base
from tests_webui.regression.widgets import check_live_feed_autorefresh
from tests_webui.regression.widgets import check_not_empty_checkbox_license_plate
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state
from tests_webui.regression.widgets import check_widget_age_filter
from tests_webui.regression.widgets import check_widget_cluster_name
from tests_webui.regression.widgets import check_widget_image_quality
from tests_webui.regression.widgets import check_widget_license_plate
from tests_webui.regression.widgets import check_widget_object_notes
from tests_webui.regression.widgets import check_widget_settings_default_filter_values

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)

LIVE_FEED_THUMBNAIL_EXPECTED_ICONS = {
    consts.BASE_FACE: {'POPUP', 'CAMERA', 'OBJECT ID', 'DATETIME', 'FACE INFO'},
    consts.BASE_VEHICLE: {'DATETIME', 'VEHICLE INFO', 'CAMERA', 'LICENSE PLATE', 'POPUP', 'OBJECT ID'},
    consts.BASE_PERSON: {'DATETIME', 'CAMERA', 'OBJECT ID', 'POPUP'},
}


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Shared Live feed widget keeps location state")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_location_state_live_feed(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(object_type=base)
    test = run_test(
        check_shared_widget_keeps_location_state(widget, base, sender, timeslice=None)
    )
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Shared Live feed widget keeps camera state")
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_camera_state_live_feed(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(object_type=base)
    test = run_test(
        check_shared_widget_keeps_camera_state(widget, base, sender, timeslice=None)
    )
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check icons in live feed widget and appearance page for {base}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1057")
@pytest.mark.parametrize('base', ['face', 'vehicle', 'person'])
def test_live_feed_objects_icons(sender, metapix, base):
    sender.check_min_objects_count({'face': 1, 'vehicle': 1, 'person': 1}, timeslice=None)
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, base)

    assert widget.thumbs, "There are no objects"
    assert widget.thumbs[0].icons_schema == LIVE_FEED_THUMBNAIL_EXPECTED_ICONS[base]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Objects meta displayed under image and matches to expected meta for {object_type}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1052")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/443')
@pytest.mark.parametrize(
    "object_type,filters",
    [
        ("face-male", consts.FILTER_MALE),
        ("vehicle-type-sedan", consts.FILTER_SEDAN),
        ("person", {}),
    ],
    ids=['face', 'vehicle', 'person'],
)
def test_live_feed_meta(sender, metapix, object_type, filters):
    # TODO: set cluster name and check meta (https://metapix-workspace.slack.com/archives/C03KBMWC146/p1693902804603219)
    sender.send(object_type)  # make sure the last object has required meta
    base, _, attribute = parse_object_type(object_type)
    attribute = attribute or ""  # prevent error: 'NoneType' object has no attribute 'upper'

    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, base)
    widget.open_settings().set_filters(filters).apply()

    check_card_meta(widget.thumbs[0].meta_text, expected_meta_thumbnail(attribute, widget.thumbs[0].id), base)

    # make sure camera doesn't disappear if only one camera is selected
    # reverted https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/153
    widget.set_filters(cameras=['camera-1'])
    check_card_meta(widget.thumbs[0].meta_text, expected_meta_thumbnail(attribute, widget.thumbs[0].id), base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Filtering objects by cameras in Live Feed Widget for {base}")
@pytest.mark.parametrize("base", ["face", "vehicle", "person"])
def test_live_feed_filter_by_camera(sender, metapix, base):
    sender.check_diff_objects_count_in_cameras(base, ["camera-1"], ['camera-1', "camera-2"], timeslice=None)
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(base)

    # only camera-1
    widget.set_filters(cameras=['camera-1'])
    assert widget.objects_count == sender.objects_count(base, cameras="camera-1", timeslice=None)

    # camra-1 + camera-2
    widget.set_filters(cameras=['camera-1', 'camera-2'])
    assert widget.objects_count == sender.objects_count(base, cameras=["camera-1", "camera-2"], timeslice=None)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Filtering objects by locations in Live Feed Widget for {base}")
@pytest.mark.parametrize("base", ["face", "vehicle", "person"])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_live_feed_filter_by_location(sender, metapix, base):
    loc_to_cameras = {
        'loc-1': ["camera-1", "camera-3"],
        'loc-2': ["camera-2"],
    }
    sender.check_diff_objects_count_in_cameras(
        base,
        loc_to_cameras["loc-1"], loc_to_cameras["loc-2"],
        timeslice=None,
    )
    create_location_schema_api(sender.client, loc_to_cameras)

    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(base)

    # loc-1
    widget.set_filters(locations=['loc-1'])
    assert widget.objects_count == sender.objects_count(
        base, cameras=loc_to_cameras["loc-1"], timeslice=None)

    # loc1 + loc2
    widget.set_filters(locations=['loc-1', 'loc-2'])
    assert widget.objects_count == sender.objects_count(
        base, cameras=loc_to_cameras["loc-1"] + loc_to_cameras["loc-2"], timeslice=None)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/619")
@allure.title("Filtering objects by empty location in Feed Widget")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_live_feed_filter_by_empty_location(sender, metapix):
    create_location_schema_api(sender.client, {"loc-empty": []})
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget("person")

    # FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1668771973927219
    check_filtering_with_empty_location(widget.open_settings().open_camera_picker(), 'loc-empty')


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Autorefresh works in live feed for {object_type}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/notification-manager/-/issues/40")
@pytest.mark.parametrize("object_type", ["face-female", "vehicle-type-sedan"])
def test_live_feed_autorefresh_not_shared(sender, metapix, object_type):
    # FYI: test for persons is in smoke suite
    check_live_feed_autorefresh(metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Autorefresh works in shared live feed for {object_type}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/notification-manager/-/issues/40")
@pytest.mark.parametrize("object_type", ["face-male", "person"])
def test_live_feed_autorefresh_shared(sender, metapix, another_driver, object_type):
    check_live_feed_autorefresh(metapix, object_type, sender, another_driver)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Objects arrive if Settings->Base has been changed")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/618")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/653")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/857")
def test_live_feed_objects_arrive_after_base_was_changed(sender, metapix):
    check_change_base(sender, metapix, consts.WIDGET_LIVE_FEED, ["face", "vehicle", "person"], wait_autorefresh_time=False, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check objects count for  Settings -> Source image quality (Good/Bad/All): {base}")
@pytest.mark.parametrize("base", [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON])
def test_live_feed_img_quality(metapix, sender, base):
    check_widget_image_quality(metapix, sender, base, consts.WIDGET_LIVE_FEED, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check Live feed header buttons")
def test_live_feed_header_icons(metapix, sender):
    sender.check_min_objects_count({"vehicle": 1}, timeslice=None)
    widget = metapix.dashboard.open_widget_builder(). \
        create_live_feed_widget(object_type="vehicle")

    assert widget.header_buttons_schema == ["AUTOREFRESH", "ZOOM IN", "MORE"]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check Live feed settings filters")
def test_live_feed_settings_filters(metapix):
    check_widget_settings_default_filter_values(
        metapix.dashboard.open_widget_builder().
        create_live_feed_widget(object_type="vehicle"),
        is_live_feed=True,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/694")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1513')
@allure.title("Timestamp conversion in shared live feeds in another time zone")
def test_timezone_in_shared_live_feed_widget(metapix, sender, another_driver):
    auth_user_in_browser(another_driver)
    sender.check_min_objects_count({"vehicle": 1})
    widget = metapix.dashboard.open_widget_builder().\
        create_live_feed_widget(object_type="vehicle")

    shared_widget = widget.share(another_driver)
    assert shared_widget.thumbs[0].meta_text == widget.thumbs[0].meta_text


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/439")
@allure.title("Popup shouldn't disappear if the related object card becode hidden")
def test_live_feed_popup_should_not_disappear_if_related_card_become_hidden(metapix, sender):
    sender.check_min_objects_count({"person": 1}, timeslice=None)
    widget = metapix.dashboard.open_widget_builder().\
        create_live_feed_widget(object_type='person')
    object_amount_required = 32 - len(widget.thumbs) + 1  # '32' is maximum amount of objects in live feed widget
    popup = widget.thumbs[-1].open_popup()
    sender.send("person", count=object_amount_required)

    with allure.step('Check popup is still exists'):
        try:
            popup.close()
        except NoElementException:
            pytest.fail("Object card popup disappeared")


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check age filter for live feed")
def test_live_feed_age_filter(metapix, sender):
    check_widget_age_filter(metapix, sender, consts.WIDGET_LIVE_FEED)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check 'cluster name' filter in live feed builder and settings for {templates}")
@pytest.mark.parametrize(
    'templates',
    [
        pytest.param(('face-male', 'face-female'), marks=pytest.mark.clusterization_faces),
        ('vehicle-type-truck', 'vehicle-type-suv'),
    ],
    ids=['face', 'vehicle'],
)
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_live_feed_cluster_name(metapix, sender, templates):
    check_widget_cluster_name(metapix, sender, consts.WIDGET_LIVE_FEED, templates)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check 'object notes' filter in live feed builder and settings")
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_live_feed_object_notes(metapix, sender, base):
    check_widget_object_notes(metapix, sender, consts.WIDGET_LIVE_FEED, base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.title("Check 'license plate' filter in live feed builder and settings")
def test_live_feed_license_plate(metapix, sender):
    check_widget_license_plate(metapix, sender, consts.WIDGET_LIVE_FEED)


@allure.epic("Frontend")
@allure.tag('bug')
@allure.suite("Widgets")
@allure.story("Live feeds")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/notification-manager/-/issues/66')
@allure.title("Sockets receives messages if there are cameras/locations filter is set")
@pytest.mark.parametrize('base', ['face'])
def test_live_receives_objects_if_camera_filter_is_set(metapix, sender, base):
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_live_feed_widget(base)
    widget.set_filters(cameras=['camera-2'])
    expected_objects_count = widget.objects_count + 1
    sender.send(base, camera='camera-2')
    widget.assert_objects_count(expected_objects_count)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('Autorefresh button has update date')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
def test_live_feed_autorefresh_timestamp(metapix, sender):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1701964330918159 '''
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_live_feed_widget('face')

    with allure.step('Check autorefresh date change if new object arrives'):
        date_start = parse_widget_updated_date(widget)
        sender.send('face')
        date_current = parse_widget_updated_date(widget)
        assert 0 < (date_current - date_start).total_seconds() < 20

    with allure.step('Additional information disappeared if autorefresh is disabled'):
        widget.disable_autorefresh()
        assert get_hover_tooltip(metapix, widget.button_autorefresh.root) == 'ENABLE AUTO REFRESH'


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('"No data" caption should be displayed if there is no data')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1223')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1267')
def test_live_feed_no_data(metapix):
    ''' Similar to `test_live_feed_items_grid_is_empty` '''
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, 'face')
    widget.open_settings(). \
        set_filters({consts.FILTER_OBJECTS_NAME: '*'}). \
        apply()

    assert widget.text == 'No Data to Display'


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('The widget does not display objects that do not match the filter results')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1203')
@pytest.mark.parametrize('base', ['face'])
def test_live_feed_items_grid_is_empty(metapix, sender, base):
    ''' Similar to `test_live_feed_no_data` '''
    sender.check_min_objects_count({'face-male': 2, 'face-female': 2, 'vehicle': 2, 'person': 2}, timeslice=None)
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, base)
    assert widget.thumbs

    widget.open_settings(). \
        set_filters({consts.FILTER_OBJECTS_NAME: 'deadbeef'}). \
        apply()
    assert not widget.thumbs


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('It is possible to zoom live feed object cards')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1299')
@pytest.mark.parametrize('base', ['face'])
def test_live_feed_zoom(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, base)
    check_zoom(widget, check_state_persistence=True)


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('Widgets: "Not empty" checkboxes work for license plate for live feed')
def test_widget_not_empty_checkbox_license_plate_live_feed(metapix, sender):
    check_not_empty_checkbox_license_plate(metapix, sender, consts.WIDGET_LIVE_FEED, {"meta": consts.META_LIC_PLATE_ANY, "timeslice": None})


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Live feeds')
@allure.title('Check tooltips for meta information in object thumbnail: live feed')
@pytest.mark.parametrize('base', ['vehicle'])
def test_object_thumb_meta_tooltips_live_feed(sender: ImageSender, metapix: RootPage, base: BaseType):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({base: 1}, timeslice=None)
        widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, base)

    with allure.step('Check tooltips thumnail in live feed'):
        thumb = widget.thumbs[0]
        check_thumbnail_meta_tooltips(thumb, base, get_object(sender.client, thumb.id))
