import itertools
import logging
import time
from typing import Iterable

import allure
import pytest

import consts
from tools import PreconditionException
from tools import are_dicts_equal
from tools import parse_object_type
from tools.image_sender import ImageSender
from tools.objects import change_cluster_name
from tools.objects import change_object_notes
from tools.search import search_api_v2
from tools.steps import check_filtering_with_empty_location
from tools.steps import create_location_schema_api
from tools.steps import create_widget_api
from tools.steps import fill_intervals_with_objects
from tools.steps import get_hover_tooltip
from tools.steps import make_cluster_api
from tools.time_tools import Ago
from tools.time_tools import filter_objects_by_timeslice
from tools.time_tools import timestamp_to_date
from tools.types import BaseType
from tools.types import WidgetType
from tools.types import ImageTemplateType
from tools.users import auth_user_in_browser

from pages.root import RootPage
from pages.base_page import is_element_exist
from pages.dashboard import NoAddWidgetButtonException
from pages.widgets import NotSharedChart
from pages.widgets import LineChartNotShared
from pages.widgets import BarChartNotShared

from tests_webui.regression import check_autorefresh_delta

log = logging.getLogger('widgets')


def check_delete_widget(layout, widget, **kwargs):
    expected_titles = layout.widgets_titles
    assert len(expected_titles) > 0
    expected_titles.remove(widget.title)

    widget.delete()  # FYI: `delete` method checks for error tooltips

    with allure.step('Check widget deleted from layout'):
        assert layout.widgets_titles == expected_titles


def check_widget_autorefresh(chart_type, metapix, object_type, sender):
    """
    1. Check that autorefresh is not enabled by default.
    2. Send an image object and check that object count has not been changed.
    3. Enable autorefresh, send one more image object and ensure that object count has risen by two.
    """
    base = parse_object_type(object_type)[0]
    sender.check_min_objects_count({object_type: 1})  # prevent NoDataFoundException
    widget = metapix.open_dashboard(). \
        open_widget_builder(). \
        create_widget(widget_type=chart_type, object_type=object_type)

    with allure.step('Object do not arrive if autorefresh is disabled'):
        widget.assert_autorefresh_disabled()
        sender.send(object_type)
        sender.wait_autorefresh_time()
        widget.assert_objects_count(sender.objects_count(base) - 1)

    with allure.step('Enable autorefresh, send one more object and ensure that 2 objects arrived'):
        widget.enable_autorefresh()
        sender.send(object_type)
        sender.wait_autorefresh_time()
        widget.assert_objects_count(sender.objects_count(base))

    with allure.step('Disable autorefresh, send one more object and ensure that object did not arrive'):
        widget.disable_autorefresh()
        sender.send(object_type)
        sender.wait_autorefresh_time()
        widget.assert_objects_count(sender.objects_count(base) - 1)


def check_filter_by_camera(chart_type, metapix, object_type, sender):
    base = parse_object_type(object_type)[0]
    sender.check_diff_objects_count_in_cameras(object_type, "camera-1", "camera-2")
    widget = metapix.dashboard.open_widget_builder(). \
        create_widget(widget_type=chart_type, object_type=object_type)

    # only "camera-1"
    widget.set_filters(cameras=['camera-1'])
    widget.assert_objects_count(sender.objects_count(base, cameras="camera-1"))

    # "camera-1" + "camera-2"
    widget.set_filters(cameras=['camera-1', 'camera-2'])
    widget.assert_objects_count(sender.objects_count(base, cameras=["camera-1", "camera-2"]))


def check_filter_by_empty_location(metapix, sender, widget_type, base):
    sender.check_min_objects_count({base: 1})
    create_location_schema_api(sender.client, {'loc-empty': []})
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_widget(widget_type=widget_type, object_type=base)

    check_filtering_with_empty_location(widget.open_settings().open_camera_picker(), 'loc-empty')


def check_filter_by_locations(chart_type, client, metapix, base, sender):
    loc_to_cameras = {
        "loc-1": ["camera-1", "camera-2"],
        "loc-2": ["camera-3"],
    }
    sender.check_diff_objects_count_in_cameras(base, loc_to_cameras["loc-1"], loc_to_cameras["loc-2"])

    create_location_schema_api(client, loc_to_cameras)
    widget = create_widget_api(metapix.dashboard, chart_type, base)
    for location in loc_to_cameras:
        widget.set_filters(locations=[location])
        widget.assert_objects_count(sender.objects_count(base, cameras=loc_to_cameras[location]))

    widget.set_filters(locations=['loc-1', 'loc-2'])
    widget.assert_objects_count(sender.objects_count(base, cameras=['camera-1', 'camera-2', 'camera-3']))


def check_widget_looks_same_after_changing_base(sender, another_base, chart_type, initial_base, metapix):
    sender.check_diff_objects_count(["vehicle", "face", "person"])
    widget = metapix.dashboard.open_widget_builder(). \
        create_widget(widget_type=chart_type, object_type=initial_base)
    initial_state = widget.state
    widget.open_settings().select_base(another_base).apply()
    widget.open_settings().select_base(initial_base).apply()
    assert are_dicts_equal(initial_state, widget.state)


def update_only_existing_keys(d_target, d_source):
    for key in d_target:
        if key in d_source:
            d_target[key] = d_source[key]
    return d_target


def restore_widget_default_settings(widget, base, filters):
    default_values = {
        'face': consts.FILTER_ANY_GENDER | {consts.FILTER_OBJECTS_NAME: ''},
    }
    with allure.step('Restore default settings'):
        log.info(f'Restore default settings of {widget}')
        assert base == 'face'
        filters_to_restore = update_only_existing_keys(filters.copy(), default_values[base])
        widget.open_settings(). \
            set_filters(filters_to_restore). \
            apply()


def restore_widget_default_camera_filters(widget):
    with allure.step('Restore default camera/location'):
        log.info(f'Restore default camera/location settings of {widget}')
        settings = widget.open_settings()
        settings.open_camera_picker(). \
            clear_all(). \
            select_all(). \
            apply()
        settings.apply()


def restore_widget_default_legend(widget):
    with allure.step('Restore default legend state'):
        log.info(f'Restore default legend state of {widget}')
        for legend_button in widget.legend:
            if not legend_button.is_enabled():
                legend_button.switch()
        time.sleep(2)


def restore_widget_default_timeslice_and_detalization(widget):
    with allure.step('Restore default timeslice and detalization'):
        log.info(f'Restore default timeslice and detalization for {widget}')
        if widget.type == consts.WIDGET_LIVE_FEED:
            raise RuntimeError(f'{widget} does not have a timeslice')
        if widget.selected_timeslice_value != consts.DEFAULT_TIMESLICE:
            widget.set_timeslice(consts.DEFAULT_TIMESLICE)
        else:
            if widget.type in (consts.WIDGET_BAR_CHART, consts.WIDGET_LINE_CHART):
                default_detalization = consts.TIMESLICE_DETAILS[consts.DEFAULT_TIMESLICE][0]
                if widget.detalization_value != default_detalization:
                    widget.set_detalization(default_detalization)


def check_original_widget_and_shared_does_not_affect_each_other_timeslice(
        sender: ImageSender, base: BaseType) -> None:
    '''
    Change default timeslice (12h) to 1w
    '''
    with allure.step('Fill timeslices with data'):
        sender.objects_count_in_interval(base, Ago('-1w'), Ago('-12h'), min_objects_count=1)
        sender.objects_count_in_interval(base, Ago('-12h'), None, min_objects_count=1)

    widget_to_change, widget_untouched = yield

    with allure.step('Change timeslice and check state of another widget'):
        widget_untouched_expected_state = widget_untouched.state
        widget_to_change.set_timeslice("1w")
        assert are_dicts_equal(widget_untouched.state, widget_untouched_expected_state)


def check_original_widget_and_shared_does_not_affect_each_other_autorefresh(
        sender: ImageSender, base: BaseType, **sender_kwargs) -> None:
    with allure.step('Make sure there are some objects'):
        sender.check_min_objects_count({base: 1}, **sender_kwargs)

    widget_to_change, widget_untouched = yield

    widget_to_change.disable_autorefresh()
    sender.send(base)
    sender.wait_autorefresh_time()
    widget_untouched.assert_objects_count(sender.objects_count(base, **sender_kwargs))
    widget_to_change.assert_objects_count(sender.objects_count(base, **sender_kwargs) - 1)


def check_original_widget_and_shared_does_not_affect_each_other_legend(
        sender: ImageSender, base: BaseType, **sender_kwargs) -> None:
    with allure.step('Check there are enough data to check legend'):
        sender.check_min_objects_count({vehicle: 1 for vehicle in consts.VEHICLE_TYPE_TEMPLATES})
        sender.check_min_objects_count({gender: 1 for gender in consts.FACE_GENDERS})

    widget_to_change, widget_untouched = yield
    widget_untouched_original_state = widget_untouched.state
    assert len(widget_to_change.legend) > 1  # self check
    assert len(widget_to_change.legend) == len(widget_untouched.legend)  # self check

    with allure.step('Change state of every legend button in original widget and check state of another widget'):
        for legend_button in widget_to_change.legend:
            legend_button.switch()
        widget_untouched.refresh()
        assert are_dicts_equal(widget_untouched.state, widget_untouched_original_state)


def check_original_widget_and_shared_does_not_affect_each_other_camera(
        sender: ImageSender, base: BaseType, **sender_kwargs) -> None:
    # TODO: it would be better to use 'objects_schema'
    with allure.step('Make sure all cameras have some data'):
        sender.check_diff_objects_count_in_cameras(base, "camera-1", "camera-2", "camera-3", **sender_kwargs)

    widget_to_change, widget_untouched = yield
    expected_objects_count = widget_untouched.objects_count

    with allure.step('Change camera filters in original the widget and check state of another widget'):
        widget_to_change.set_filters(cameras=['camera-2', 'camera-3'])
        widget_untouched.refresh()
        widget_untouched.assert_objects_count(expected_objects_count)


def check_original_widget_and_shared_does_not_affect_each_other_location(
        sender: ImageSender, base: BaseType, **sender_kwargs) -> None:
    '''
    I think we may not count right amount of objects due to we here check
    is original widget can affect shared widget
    '''
    loc_schema = {
        "loc-1": ["camera-1", "camera-3"],
        "loc-2": ["camera-2"],
    }
    with allure.step('Make sure all locations have some data'):
        sender.check_diff_objects_count_in_cameras(base, loc_schema["loc-1"], loc_schema["loc-2"], **sender_kwargs)
        create_location_schema_api(sender.client, loc_schema)

    widget_to_change, widget_untouched = yield
    expected_objects_count = widget_untouched.objects_count

    with allure.step('Change locs filters in original widget and check state of another widget'):
        widget_to_change.set_filters(locations=['loc-2'])
        widget_untouched.refresh()
        widget_untouched.assert_objects_count(expected_objects_count)


def check_original_widget_and_shared_does_not_affect_each_other_settings(widget_to_change, widget_untouched, sender, base, **kwargs):
    """
    Doesn't suit pie chart because it doesn't have the filters.
    """
    if base == 'vehicle':
        filters = consts.FILTER_SEDAN
    elif base == 'face':
        if widget_to_change.type == consts.WIDGET_PIE_CHART:
            filters = {consts.FILTER_OBJECTS_NAME: 'Test'}  # PIE chart doesn't have 'Gender' filter
        else:
            filters = consts.FILTER_MALE
    else:
        raise RuntimeError('Unexpected behavior')
    with allure.step('Change settings'):
        sender.check_diff_objects_count([
            "face-male",
            "face-female",
            "vehicle-type-sedan",
            "vehicle-type-van",
            "person",
        ], **kwargs)
        widget_to_change.refresh()
        widget_untouched.refresh()

        widget_untouched_original_state = widget_untouched.state
        widget_to_change.open_settings(). \
            set_filters(filters). \
            apply(delay=5)
        assert are_dicts_equal(widget_untouched_original_state, widget_untouched.state)

        # teardown
        restore_widget_default_settings(widget_to_change, base, filters)


def check_original_widget_and_shared_does_not_affect_each_other_changing_base(
        sender: ImageSender, base: BaseType, **sender_kwargs):
    with allure.step('Make sure there are some objects of every base'):
        sender.check_diff_objects_count(["face", "vehicle", "person"], **sender_kwargs)
        bases = ['face', 'vehicle', 'person']

    widget_to_change, widget_untouched = yield
    if widget_to_change.type == consts.WIDGET_PIE_CHART:
        bases.remove('person')
    bases.remove(base)
    widget_untouched_expected_state = widget_untouched.state

    while bases:
        with allure.step(f'Check changing base to {bases[0]}'):
            widget_to_change.open_settings().select_base(bases.pop()).apply()
            widget_untouched.refresh()
            assert are_dicts_equal(widget_untouched.state, widget_untouched_expected_state)


def check_legend_colors_are_different(widget: NotSharedChart, base: BaseType):
    '''
    Pie chart displays only 2 sectors for faces: male and female. Thus we don't need to send every
    face from face/ages directory
    '''
    with allure.step('Check legend size'):
        if base == 'vehicle':
            # FYI: 2w timeslice doesn't have "wagon" vehicles... so minu 1
            assert len(widget.legend) >= len(consts.VEHICLE_TYPE_TEMPLATES) - 1
        else:
            if widget.type == consts.WIDGET_PIE_CHART:
                if len(widget.legend) not in (2, 3):
                    raise PreconditionException('Legend should have 2 or 3 entities: male, female, undefined')
            else:
                # TODO: find out the exect amount of age images
                if len(widget.legend) < 10:
                    raise PreconditionException('Legend should have at least 10 entities')

    with allure.step('Check legend buttons color'):
        for first_legend, second_legend in itertools.pairwise(widget.legend):
            with allure.step(f'Check {first_legend} vs {second_legend}'):
                log.info(f'Check {first_legend} vs {second_legend}')
                assert first_legend.color != second_legend.color, \
                    f"{first_legend.name} and {second_legend.name} have the same color"


def check_shared_widget_keeps_camera_state(widget, base, sender, check_settings=False, **kwargs):
    sender.check_diff_objects_count_in_cameras(base, "camera-1", "camera-2", "camera-3", **kwargs)

    selected_cameras = ['camera-1', 'camera-2']
    widget.set_filters(cameras=selected_cameras)
    shared_widget = yield
    shared_widget.assert_objects_count(sender.objects_count(base, cameras=selected_cameras, **kwargs))

    if check_settings:
        with allure.step(f'Check camera settings for {shared_widget}'):
            filter_dialog = widget.open_settings(). \
                open_camera_picker()
            assert filter_dialog.schema == ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☐', 'camera-4 ☐']


def check_shared_widget_keeps_location_state(widget, base, sender, check_settings=False, **kwargs):
    loc_to_cameras = {
        "loc-1": ["camera-1", "camera-3"],
        "loc-2": ["camera-2"],
    }
    sender.check_diff_objects_count_in_cameras(base, loc_to_cameras["loc-1"], loc_to_cameras["loc-2"], **kwargs)
    create_location_schema_api(sender.client, loc_to_cameras)

    widget.set_filters(locations=['loc-1'])
    shared_widget = yield
    shared_widget.assert_objects_count(sender.objects_count(base, cameras=loc_to_cameras['loc-1'], **kwargs))

    if check_settings:
        with allure.step(f'Check location settings for {shared_widget}'):
            filter_dialog = shared_widget.open_settings(). \
                open_camera_picker()
            assert filter_dialog.schema == [
                {'▼ loc-1 ☑': []},
                {'▼ loc-2 ☐': []},
                'camera-4 ☐',
            ]


def check_live_feed_autorefresh(metapix, object_type, sender, another_driver=None):
    def check_objects_count(widget, expected_count):
        widget.assert_objects_count(expected_count)

    base = parse_object_type(object_type)[0]
    sender.check_min_objects_count({base: 1}, timeslice=None)
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_LIVE_FEED, object_type)
    widget.assert_autorefresh_enabled()
    if another_driver:
        auth_user_in_browser(another_driver)
        widget = widget.share(another_driver)
    check_objects_count(widget, sender.objects_count(base, timeslice=None))

    with allure.step("Object has arrived (autorefresh is enabled)"):
        sender.send(object_type)
        check_objects_count(widget, sender.objects_count(base, timeslice=None))

    with allure.step("Object hasn't arrived after disable autorefresh"):
        widget.disable_autorefresh()
        sender.send(object_type)
        check_objects_count(widget, sender.objects_count(base, timeslice=None)-1)

    with allure.step("Check only one object has arrived after enable autorefresh"):
        # FYI: https://metapix-workspace.slack.com/archives/C03KQ8KP9BP/p1698418775947079
        widget.enable_autorefresh()
        sender.send(object_type)
        check_objects_count(widget, sender.objects_count(base, timeslice=None)-1)

    with allure.step("Check widget displays all objects after refresh"):
        widget.refresh()
        check_objects_count(widget, sender.objects_count(base, timeslice=None))


def check_change_base(
        sender: ImageSender,
        metapix: RootPage,
        widget_type: WidgetType,
        object_types: Iterable[ImageTemplateType],
        wait_autorefresh_time: bool = True,
        enable_autorefresh: bool = False, **kwargs) -> None:
    sender.check_diff_objects_count(["face", "vehicle", "person"], min_count=2, **kwargs)
    widget = create_widget_api(metapix.dashboard, widget_type, object_types[0])
    if enable_autorefresh:
        widget.enable_autorefresh()

    for _ in range(len(object_types)):
        object_types = object_types[1:] + [object_types[0]]
        base = parse_object_type(object_types[0])[0]

        # check widget changes its content after base change
        widget.open_settings().select_base(base).apply()
        if wait_autorefresh_time:
            sender.wait_autorefresh_time()
        widget.assert_objects_count(sender.objects_count(base, **kwargs))

        # check objects arrive after base change
        for object_type in object_types:
            sender.send(object_type, get_meta=False)
        sender.get_meta_information_from_backend()
        if wait_autorefresh_time:
            sender.wait_autorefresh_time()
        widget.assert_objects_count(sender.objects_count(base, **kwargs))


def check_is_not_possible_to_create_widget(layout, **kwargs):
    assert not is_element_exist(
        lambda: layout.button_add_widget,
        custom_exception=NoAddWidgetButtonException,
    )


def check_filtering_works(sender, widget, base, **kwargs):
    sender.check_diff_objects_count_in_cameras(base, "camera-1", "camera-2")
    widget.refresh()  # widgets don't have autorefresh enabled by default (except live feed)
    widget.assert_objects_count(sender.objects_count(base))
    widget.set_filters(cameras=['camera-1'])
    widget.assert_objects_count(sender.objects_count(base, cameras="camera-1"))

    # teardown
    restore_widget_default_camera_filters(widget)


def check_autorefresh_works(sender, widget, base, **kwargs):
    if widget.type == consts.WIDGET_VALUE:
        pytest.skip(f'{widget.type} widget does not support auto refresh')
    widget.assert_objects_count(sender.objects_count(base))

    if widget.type != consts.WIDGET_LIVE_FEED:
        widget.enable_autorefresh()
    sender.send(base)
    sender.wait_autorefresh_time()
    widget.assert_objects_count(sender.objects_count(base))

    widget.disable_autorefresh()
    sender.send(base)
    sender.wait_autorefresh_time()
    widget.assert_objects_count(sender.objects_count(base) - 1)


def check_change_timeslice(sender, widget, base, do_teardown=True, **kwargs):
    data = {
        '1h': (Ago('-1h'), None),  # from...to
        '6h': (Ago('-6h'), Ago('-1h')),
        '12h': (Ago('-12h'), Ago('-6h')),
    }
    for delta_1, delta_2 in data.values():
        sender.objects_count_in_interval(base, delta_1, delta_2, min_objects_count=1)

    # NB: we don't need to wait autorefresh time:
    # widget sends request every time you switch timeslice

    for timeslice in data:
        with allure.step(f'Check timeslice {timeslice}'):
            log.info(f'Check timeslice {timeslice}')
            widget.set_timeslice(timeslice)
            widget.assert_objects_count(sender.objects_count(base, timeslice=timeslice))

    # teardown
    if do_teardown:
        restore_widget_default_timeslice_and_detalization(widget)


def check_is_possible_to_rename_widget(
        widget,
        new_title: str = 'Test title',
        refresh_check: bool = True,
        **kwargs,
):
    """
    https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/665
    I am going to disable this check because:
     - to be able to run tests
     - seems like we are going to forbid editing title on shared layout
    FIY:
      https://metapix-workspace.slack.com/archives/C03KBMWC146/p1669813158011269
      https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1707823456410749
    """
    with allure.step(f'Rename {widget} -> "{new_title}"'):
        widget.enter_edit_title_mode()
        widget.set_title(new_title)
        widget.confirm_title()
        assert widget.header_text == new_title

    if refresh_check:
        with allure.step('Check widget title after refresh'):
            widget.refresh()
            assert widget.header_text == new_title


def check_widget_image_quality(metapix, sender, base, widget_type, **kwargs):
    """
    This test isn't suitable for pie chart (it doesn't have filters)
    """
    sender.check_diff_objects_count([f"{base}-bad-quality", f"{base}-good-quality"])

    with allure.step('It is possible to set bad quality in widget builder'):
        widget = metapix.dashboard.open_widget_builder(). \
            create_widget(
                widget_type=widget_type,
                object_type=base,
                filters=consts.FILTER_BAD_QUALITY,
            )
        widget.assert_objects_count(sender.objects_count(base, consts.META_BAD_QUALITY, **kwargs))

    with allure.step('Is is possible to set all image quality in widget settings'):
        widget.open_settings(). \
            set_filters(consts.FILTER_ANY_QUALITY). \
            apply()
        widget.assert_objects_count(sender.objects_count(base, consts.META_ANY_QUALITY, **kwargs))


def check_widget_settings_default_filter_values(widget, is_live_feed=False, is_pie_chart=False):
    """
    FYI: filters for pie chart: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/376
    """
    # TODO: `is_live_feed` is useless parameter right now
    settings = widget.open_settings()

    def get_expected_filters_schema(base, widget_type):
        expected_schema = {
            consts.FILTER_OBJECTS_NAME: '',
            consts.FILTER_OBJECTS_NOTES: '',
            consts.FILTER_CAMERAS_LOCATIONS: 'Filtered by: 4 Cameras',
        } | consts.FILTER_GOOD_QUALITY
        expected_schema[consts.FILTER_BASE] = base.capitalize()
        if base == 'face':
            expected_schema[consts.FILTER_AGE] = (0, 100)
            if widget_type != consts.WIDGET_PIE_CHART:
                expected_schema |= consts.FILTER_ANY_GENDER
        if base == 'vehicle':
            expected_schema[consts.FILTER_LICENSE_PLATE] = ''
            if widget_type != consts.WIDGET_PIE_CHART:
                expected_schema |= consts.FILTER_ANY_VEHICLE
        return expected_schema

    def _check_base(base, widget_type):
        with allure.step(f'Check filters for {base}'):
            settings.select_base(base)
            assert settings.filters_schema == get_expected_filters_schema(base, widget_type)

    _check_base('face', widget.type)
    _check_base('vehicle', widget.type)
    if not is_pie_chart:
        _check_base('person', widget.type)


def check_hide_show_legend(widget):
    with allure.step('Check there is a legend by default'):
        assert widget.legend
        legend_schema = widget.legend_schema

    with allure.step('Check it is possible to disable legend'):
        widget.disable_legend()
        assert not widget.legend

    with allure.step('Check changes (disabled legend) persist'):
        widget.refresh()
        assert not widget.legend

    with allure.step('Check it is possible to enable legend'):
        widget.enable_legend()
        assert widget.legend_schema == legend_schema

    with allure.step('Check changes (enabled legend) persist'):
        widget.refresh()
        assert widget.legend


def check_hide_show_timeslice(sender, widget, base, change_detalization):
    with allure.step('Set non default values for timeslice and detalization'):
        # We need at leat 1 object in -1w..-12h interval
        # chart state should change during switching timeslice
        # Check `change_timeslice` method
        sender.objects_count_in_interval(base, Ago('-1w'), Ago('-12h'), min_objects_count=1)

        assert is_element_exist(lambda: widget.timeslice_container) is True
        widget.set_timeslice('1w')     # 12h by default
        if change_detalization:
            widget.set_detalization('1d')

    expected_timeslice_schema = widget.timeslice_schema
    with allure.step('Check it is possible to disable timeslice'):
        widget.disable_time_intervals()
        assert is_element_exist(lambda: widget.timeslice_container) is False

    with allure.step('Check changes (disabled timeslice) persist'):
        widget.refresh()
        assert is_element_exist(lambda: widget.timeslice_container) is False

    with allure.step('Check it is possible to enable timeslice'):
        widget.enable_time_intervals()
        assert is_element_exist(lambda: widget.timeslice_container) is True
        assert widget.timeslice_schema == expected_timeslice_schema

    with allure.step('Check changes (enabled timeslice) persist'):
        widget.refresh()
        assert is_element_exist(lambda: widget.timeslice_container) is True
        assert widget.timeslice_schema == expected_timeslice_schema

    check_change_timeslice(sender, widget, base)


def check_widget_age_filter(metapix, sender, widget_type):
    sender_kwargs = {'timeslice': None} if widget_type == consts.WIDGET_LIVE_FEED else {}
    sender.check_diff_objects_count(['face-30-age', 'face-70-age'])
    widget = create_widget_api(metapix.dashboard, widget_type, 'face')

    with allure.step('Use age filter in widget builder'):
        widget.open_settings(). \
            set_filters({consts.FILTER_AGE: (0, 50)}). \
            apply()
        widget.assert_objects_count(sender.objects_count_for_ages(0, 50, **sender_kwargs))

    with allure.step('Use age filter in widget settings'):
        widget.open_settings(). \
            set_filters({consts.FILTER_AGE: (50, 100)}). \
            apply()
        widget.assert_objects_count(sender.objects_count_for_ages(50, 100, **sender_kwargs))


def check_widget_cluster_name(metapix, sender, widget_type, templates):
    '''
    Merged with test `test_widget_not_empty_checkboxes_cluster_names`
    https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/568
    https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/296

    For faces: every cluster has several objects
    For vehicles: find 2 objects (no clusterization for vehicles)
    '''
    timeslice = None if widget_type == consts.WIDGET_LIVE_FEED else consts.DEFAULT_TIMESLICE
    base = parse_object_type(templates[0])[0]
    with allure.step('Prepare objects'):
        if len(templates) != 2:
            raise RuntimeError
        if base == 'face':
            cluster_1 = make_cluster_api(sender, templates[0], timeslice=timeslice)
            cluster_2 = make_cluster_api(sender, templates[1], timeslice=timeslice)
        if base == 'vehicle':
            for template in templates:
                sender.check_min_objects_count({template: 1}, timeslice=timeslice)
            objects_ = filter_objects_by_timeslice(
                search_api_v2(sender.client, 'vehicle', recursive=True),
                lambda x: timestamp_to_date(x.timestamp),
                timeslice=timeslice,
            )
            cluster_1, cluster_2 = objects_[:2]
        change_cluster_name(sender.client, cluster_1, 'Cluster 1')
        change_cluster_name(sender.client, cluster_2, 'Cluster 2')

    with allure.step('Use "cluster name" filter in widget settings: "Not empty"'):
        widget = create_widget_api(metapix.dashboard, widget_type, base)
        settings = widget.open_settings()
        settings.input_object_name.checkbox.select()
        assert settings.input_object_name.value == "Not empty"
        settings.apply()
        widget.assert_objects_count(cluster_1.cluster_size + cluster_2.cluster_size)

    with allure.step('Use "cluster name" filter in widget settings: "Cluster 1"'):
        settings = widget.open_settings()
        settings.input_object_name.checkbox.unselect()
        settings.set_filters({consts.FILTER_OBJECTS_NAME: 'Cluster 1'}). \
            apply()
        widget.assert_objects_count(cluster_1.cluster_size)


def check_widget_object_notes(metapix, sender, widget_type, base):
    timeslice = None if widget_type == consts.WIDGET_LIVE_FEED else consts.DEFAULT_TIMESLICE

    with allure.step('Prepare objects'):
        sender.check_min_objects_count({base: 3}, timeslice=timeslice)
        if timeslice:
            objects = filter_objects_by_timeslice(
                search_api_v2(sender.client, base, recursive=True),
                lambda x: timestamp_to_date(x.timestamp),
                timeslice,
            )
        else:
            objects = search_api_v2(sender.client, base, recursive=True)
        assert len(objects) > 2  # self check
        for ix, obj in enumerate(objects[:2]):
            change_object_notes(sender.client, obj, f'Note {ix+1}')

    with allure.step('Use "object notes" filter in widget builder: *'):
        widget = metapix.dashboard. \
            open_widget_builder(). \
            create_widget(
                widget_type=widget_type,
                object_type=base,
                filters={consts.FILTER_OBJECTS_NOTES: '*'},
            )
        widget.assert_objects_count(2)

    with allure.step('Use "object notes" filter in widget settings: Note 1'):
        settings = widget.open_settings()
        settings.input_object_note.checkbox.unselect()
        settings.set_filters({consts.FILTER_OBJECTS_NOTES: 'Note 1'}). \
            apply()
        widget.assert_objects_count(1)


def check_widget_license_plate(metapix, sender, widget_type):
    timeslice = None if widget_type == consts.WIDGET_LIVE_FEED else consts.DEFAULT_TIMESLICE

    with allure.step('Prepare objects'):
        for lic_plate in ('12345', '54321'):
            sender.check_min_objects_count(
                {'vehicle': 1},
                meta={consts.META_LIC_PLATE: lic_plate},
                timeslice=timeslice,
            )

    with allure.step('Use "license plate" filter in widget builder: *'):
        widget = metapix.dashboard. \
            open_widget_builder(). \
            create_widget(
                widget_type=widget_type,
                object_type='vehicle',
                filters={consts.FILTER_LICENSE_PLATE: '*'},
            )
        objects_with_any_lic_plate = sender.objects('vehicle', {consts.META_LIC_PLATE: '*'}, timeslice=timeslice)
        assert len(objects_with_any_lic_plate) > 1  # self check
        widget.assert_objects_count(len(objects_with_any_lic_plate))

    with allure.step('Use "license plate" filter in widget settings: 54321'):
        settings = widget.open_settings()
        settings.input_license_plate.checkbox.unselect()
        settings.set_filters({consts.FILTER_LICENSE_PLATE: '54321'}). \
            apply()
        object_with_54321_lic_plate = sender.objects('vehicle', {consts.META_LIC_PLATE: '54321'}, timeslice=timeslice)
        assert len(object_with_54321_lic_plate) < len(objects_with_any_lic_plate)  # self check
        widget.assert_objects_count(len(object_with_54321_lic_plate))


def check_widget_timestamp_in_autorefresh_button(metapix, widget, sender):
    with allure.step('There is no information about autorefresh if autorefresh is disabled'):
        assert get_hover_tooltip(metapix, widget.button_autorefresh.root) == 'ENABLE AUTO REFRESH'

    with allure.step('Additional information appears if autorefresh is enabled'):
        # TODO: find out that this date (which appears after autorefresh has just been enabled) means
        widget.enable_autorefresh()
        check_autorefresh_delta(widget, sender)

    with allure.step('Additional information disappeared if autorefresh is disabled'):
        widget.disable_autorefresh()
        assert get_hover_tooltip(metapix, widget.button_autorefresh.root) == 'ENABLE AUTO REFRESH'


def check_timeslice_detalization(
        widget: BarChartNotShared | LineChartNotShared,
        sender: ImageSender,
):
    test_data = [
        ('1w', '1d', 7),
        ('2w', '2d', 7),
    ]
    for timeslice, detalization, expected_columns_count in test_data:
        with allure.step(f'Check {timeslice}-{detalization}'):
            fill_intervals_with_objects(sender, 'vehicle', timeslice, detalization)
            widget.set_timeslice(timeslice)
            widget.set_detalization(detalization)

            widget.assert_objects_count(sender.objects_count('vehicle', timeslice=timeslice))
            if widget.type == consts.WIDGET_BAR_CHART:
                assert len(widget.bars) == expected_columns_count  # type: ignore[reportAttributeAccessIssue]
            elif widget.type == consts.WIDGET_LINE_CHART:
                assert len(widget.lines) == expected_columns_count  # type: ignore[reportAttributeAccessIssue]
            else:
                raise RuntimeError(f'Widget {widget.type} does not have detalization')


def check_not_empty_checkbox_license_plate(metapix, sender, widget_type, sender_kwargs):
    '''
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/568
    '''
    sender.check_min_objects_count({'vehicle': 2}, **sender_kwargs)

    widget = create_widget_api(metapix.dashboard, widget_type, 'vehicle')
    settings = widget.open_settings()
    settings.input_license_plate.checkbox.select()
    assert settings.input_license_plate.value == 'Not empty'
    settings.apply()
    widget.assert_objects_count(sender.objects_count('vehicle', **sender_kwargs))
