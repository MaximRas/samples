import logging
import re
import time

import pytest
import allure

import consts
from tools import run_test
from tools import send_value_to_test
from tools.image_sender import ImageSender
from tools.steps import create_widget_api
from tools.steps import fill_intervals_with_objects
from tools.time_tools import Ago
from tools.types import BaseType
from tools.types import TimesliceType
from tools.users import auth_user_in_browser

from pages.widgets import BarChartNotShared
from pages.root import RootPage

from tests_webui.regression.widgets import check_change_base
from tests_webui.regression.widgets import check_filter_by_camera
from tests_webui.regression.widgets import check_filter_by_locations
from tests_webui.regression.widgets import check_hide_show_legend
from tests_webui.regression.widgets import check_hide_show_timeslice
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state
from tests_webui.regression.widgets import check_timeslice_detalization
from tests_webui.regression.widgets import check_widget_age_filter
from tests_webui.regression.widgets import check_widget_autorefresh
from tests_webui.regression.widgets import check_widget_timestamp_in_autorefresh_button
from tests_webui.regression.widgets import check_widget_cluster_name
from tests_webui.regression.widgets import check_widget_image_quality
from tests_webui.regression.widgets import check_widget_license_plate
from tests_webui.regression.widgets import check_widget_looks_same_after_changing_base
from tests_webui.regression.widgets import check_widget_object_notes
from tests_webui.regression.widgets import check_widget_settings_default_filter_values
from tests_webui.regression.widgets import check_not_empty_checkbox_license_plate

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Shared Bar chart widget keeps location state")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_location_state_bar_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_location_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Shared Bar chart widget keeps camera state")
@pytest.mark.parametrize('base', ['face'])
def test_shared_widget_keeps_camera_state_bar_chart(sender, metapix, another_driver, base):
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    test = run_test(check_shared_widget_keeps_camera_state(widget, base, sender))
    send_value_to_test(test, widget.share(another_driver))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Enable autorefresh and check that object count has risen for {object_type}")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-minivan", "person"])
def test_bar_chart_autorefresh(sender, metapix, object_type):
    check_widget_autorefresh(consts.WIDGET_BAR_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Filtering by cameras (bar chart) for {object_type}")
@pytest.mark.parametrize("object_type", ["face-male", "vehicle-type-wagon"])
def test_bar_chart_filter_by_camera(sender, metapix, object_type):
    check_filter_by_camera(consts.WIDGET_BAR_CHART, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Filtering by locations (bar chart) for {object_type}")
@pytest.mark.parametrize("object_type", ["face", "person"])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_bar_chart_filter_by_location(sender, metapix, client, object_type):
    check_filter_by_locations(consts.WIDGET_BAR_CHART, client, metapix, object_type, sender)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Widget looks the same after changing base and back")
@pytest.mark.parametrize("initial_base, another_base", [("face", "vehicle"), ("vehicle", "face")])
def test_widget_looks_same_after_changing_base_bar(sender, metapix, initial_base, another_base):
    check_widget_looks_same_after_changing_base(sender, another_base, consts.WIDGET_BAR_CHART, initial_base, metapix)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Objects arrive if Settings->Base has been changed")
def test_bar_chart_objects_arrive_after_base_was_changed(sender, metapix):
    check_change_base(sender, metapix, consts.WIDGET_BAR_CHART, ["face", "vehicle", "person"], enable_autorefresh=True)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Bar char should have correct hints for bars")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/402")
def test_bar_chart_hints(metapix, sender):
    sender.check_min_objects_count({gender: 1 for gender in consts.FACE_GENDERS})
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, 'face')
    amounts_from_tooltips = []
    for rect in widget.rects:
        assert re.findall(r'From: \d{2}/\d{2}/202\d \d{2}:\d{2} [AP]M', rect.tooltip[0])  # 'From: 06/08/2024 10:00 AM'
        assert re.findall(r'To: \d{2}/\d{2}/202\d \d{2}:\d{2} [AP]M', rect.tooltip[1])
        assert re.findall(r'MALE|FEMALE|UNDEFINED \((\d+-\d+|UNDEFINED)\): \d+', rect.tooltip[2])  # 'MALE (30-40): 1'
        amounts_from_tooltips.append(rect.objects_count)
    assert len(amounts_from_tooltips) >= 2
    assert sum(amounts_from_tooltips) == widget.objects_count


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Modify display of Vehicles Bars using Legend labels (type of vehicle)")
@pytest.mark.parametrize('vehicle_type', ['WAGON'])
def test_bar_chart_vehicle_disable_through_legend(metapix, sender, vehicle_type):
    sender.check_min_objects_count({vehicle: 1 for vehicle in consts.VEHICLE_TYPE_TEMPLATES})
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="vehicle")

    bar_with_wagon = [ix for ix, bar in enumerate(widget.bars) if vehicle_type in bar.legend_titles][0]

    widget.legend.get(vehicle_type).switch()
    assert vehicle_type not in widget.bars[bar_with_wagon].legend_titles
    widget.assert_objects_count(sender.objects_count('vehicle') - sender.objects_count(f'vehicle-type-{vehicle_type.lower()}'))

    widget.legend.get(vehicle_type).switch()
    assert vehicle_type in widget.bars[bar_with_wagon].legend_titles
    widget.assert_objects_count(sender.objects_count('vehicle'))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check objects count for  Settings -> Source image quality (Good/Bad/All)")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/173")
@pytest.mark.parametrize("base", [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON])
def test_bar_chart_img_quality(metapix, sender, base):
    check_widget_image_quality(metapix, sender, base, consts.WIDGET_BAR_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check Bar chart header buttons")
def test_bar_chart_header_icons(metapix):
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="vehicle")

    assert widget.header_buttons_schema == ["AUTOREFRESH", "BAR CHART", "LINE CHART", "ADJUST", "MORE"]


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check Bar chart settings filters")
def test_bar_char_settings_filters(metapix):
    check_widget_settings_default_filter_values(
        metapix.dashboard.open_widget_builder().
        create_bar_chart_widget(object_type="vehicle")
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/393")
@allure.title("Empty result in vehicle bar/line chart after changing drop-down list to All")
def test_bar_line_chart_no_results(sender, metapix):
    sender.check_diff_objects_count(["vehicle-type-sedan", "vehicle-type-truck"])
    widget = metapix.dashboard.open_widget_builder().\
        create_bar_chart_widget(object_type='vehicle')

    widget.open_settings().select_vehicle_type(consts.VEHICLE_TYPE_SEDAN).apply()
    widget.assert_objects_count(sender.objects_count("vehicle", consts.META_SEDAN))

    widget.open_settings().select_vehicle_type(consts.OPTION_ALL).apply()
    widget.assert_objects_count(sender.objects_count("vehicle"))


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check hide/show lengend works (adjust menu)")
@pytest.mark.parametrize('base', ['vehicle'])
def test_bar_chart_hide_show_legend(metapix, sender, base):
    sender.check_min_objects_count({
        'face-male': 1,
        'face-female': 1,
        'vehicle-type-sedan': 1,
        'vehicle-type-truck': 1,
    })
    check_hide_show_legend(
        metapix.dashboard.
        open_widget_builder().
        create_bar_chart_widget(object_type=base)
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check hide/show column labels works (adjust menu)")
@pytest.mark.parametrize('timeslice,detalization', [('2w', '2d')])
@pytest.mark.parametrize('base', ['vehicle'])
def test_bar_chart_hide_show_column_labels(
        metapix: RootPage, sender: ImageSender, base: BaseType, timeslice: TimesliceType, detalization: str):
    fill_intervals_with_objects(sender, base, timeslice, detalization)
    widget: BarChartNotShared = create_widget_api(metapix.dashboard, consts.WIDGET_BAR_CHART, base). \
        set_timeslice(timeslice). \
        set_detalization(detalization)
    with allure.step('Check there is a column labels by default'):
        expected_column_labels = widget.objects_count_list
        assert expected_column_labels

    with allure.step('Check it is possible to disable column labels'):
        widget.disable_column_labels()
        assert not widget.objects_count_list

    with allure.step('Check changes (disabled column labels) persist'):
        widget.refresh()
        assert not widget.objects_count_list

    with allure.step('Check it is possible to enable column labels'):
        widget.enable_column_labels()
        assert widget.objects_count_list == expected_column_labels

    with allure.step('Check changes (enabled column labels) persist'):
        widget.refresh()
        assert widget.objects_count_list == expected_column_labels


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check age filter for bar chart")
def test_bar_chart_age_filter(metapix, sender):
    check_widget_age_filter(metapix, sender, consts.WIDGET_BAR_CHART)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check 'cluster name' filter in bar chart builder and settings")
@pytest.mark.parametrize(
    'templates',
    [
        pytest.param(('face-male', 'face-female'), marks=pytest.mark.clusterization_faces),
        ('vehicle-type-truck', 'vehicle-type-suv'),
    ],
    ids=['face', 'vehicle'],
)
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_bar_chart_cluster_name(metapix, sender, templates):
    check_widget_cluster_name(metapix, sender, consts.WIDGET_BAR_CHART, templates)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check 'object notes' filter in bar chart builder and settings")
@pytest.mark.parametrize('base', ['vehicle'])
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_bar_chart_object_notes(metapix, sender, base):
    check_widget_object_notes(metapix, sender, consts.WIDGET_BAR_CHART, base)


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check 'license plate' filter in bar chart builder and settings")
def test_bar_chart_license_plate(metapix, sender):
    check_widget_license_plate(metapix, sender, consts.WIDGET_BAR_CHART)


@allure.epic("Frontend")
@allure.tag('bug')
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("The same amount of columns for chart after autorefresh (changed detalization)")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1142')
@pytest.mark.parametrize('base', ['vehicle'])
def test_bar_chart_state_after_autorefresh_changed_detalization(metapix, sender, base):
    fill_intervals_with_objects(sender, base, consts.DEFAULT_TIMESLICE, '2h')
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    widget.enable_autorefresh()
    widget.set_detalization('2h')  # 1h by default
    bars_before = len(widget.bars)

    sender.wait_autorefresh_time()
    assert len(widget.bars) == bars_before
    assert widget.detalization_value == '2h'


@allure.epic("Frontend")
@allure.tag('bug')
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("The same amount of columns for chart after autorefresh (custom timeslice)")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1142')
@pytest.mark.parametrize('base', ['vehicle'])
@pytest.mark.parametrize(
    'timeslice, detalization', [
        (Ago('-3h'), consts.HOUR_SECONDS // 2),
    ],
    ids=['3h']
)
def test_bar_chart_state_after_autorefresh_custom_timeslice(metapix, sender, base, timeslice, detalization):
    fill_intervals_with_objects(sender, base, timeslice, detalization)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    widget.enable_autorefresh()

    with allure.step('Set custom timeslice'):
        widget.set_custom_timeslice(date_from=timeslice.dt)
        expected_bars_count = len(widget.bars)

    sender.wait_autorefresh_time()
    assert len(widget.bars) == expected_bars_count


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Bar charts')
@allure.title('Autorefresh button contains additional information about autorefresh')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1016')
def test_bar_chart_timestamp_in_autorefresh_button(metapix, sender):
    check_widget_timestamp_in_autorefresh_button(
        metapix,
        metapix.dashboard.open_widget_builder().
        create_bar_chart_widget(object_type='face'),
        sender,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check hide/show timeslice works (adjust menu)")
@pytest.mark.parametrize('base', ['vehicle'])
def test_bar_chart_hide_show_timeslice(metapix, sender, base):
    check_hide_show_timeslice(
        sender,
        metapix.dashboard.
        open_widget_builder().
        create_bar_chart_widget(object_type=base),
        base,
        change_detalization=True,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.title("Check timeslice detalization for bar chart")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/411')
def test_bar_chart_timeslice_detalization(metapix, sender):
    check_timeslice_detalization(
        metapix.dashboard.open_widget_builder().
        create_bar_chart_widget(object_type='vehicle'),
        sender,
    )


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.story("Bar charts")
@allure.tag("bug")
@allure.title("Test rendering with many unkown vehicle types")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/534")
@pytest.mark.skip('I suppose this test is uselees')
def test_rendering_of_bar_charts_with_many_vehicle_unknown_types(sender, metapix):
    def check_timesclice(widget, timeslice):
        widget.set_timeslice(timeslice)
        assert widget.legend is not None
        assert sender.objects_count("vehicle", timeslice=timeslice) == widget.objects_count

    interval_1h = 60 * 360
    timestamps = [int(time.time()) - period * interval_1h for period in reversed(range(0, 4))]
    for timestamp in timestamps:
        sender.send('vehicle-type-unknown', count=40, timestamp=timestamp)

    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type="vehicle")

    check_timesclice(widget, "2w")
    check_timesclice(widget, "12h")
    check_timesclice(widget, "1d")


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.story('Bar charts')
@allure.title('Widgets: "Not empty" checkboxes work for license plate for bar chart')
def test_widget_not_empty_checkbox_license_plate_bar_chart(metapix, sender):
    check_not_empty_checkbox_license_plate(metapix, sender, consts.WIDGET_BAR_CHART, {"meta": consts.META_LIC_PLATE_ANY})
