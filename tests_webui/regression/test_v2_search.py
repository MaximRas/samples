import logging
from collections import defaultdict
from typing import Iterable

import allure
import pytest

import consts
from tools import PreconditionException
from tools import ObjectData
from tools import check_images_are_equal
from tools import check_images_are_not_equal
from tools import parse_object_type
from tools.image_sender import ImageSender
from tools.objects import change_cluster_name
from tools.objects import change_object_notes
from tools.objects import get_object
from tools.objects import get_objects_without_cluster
from tools.objects import get_suitable_objects
from tools.objects import is_head_of_cluster
from tools.objects import is_not_head_of_cluster
from tools.search import search_api_v2
from tools.steps import check_filtering_with_empty_location
from tools.steps import check_input_validation
from tools.steps import create_location_schema_api
from tools.steps import find_card_with_eye
from tools.steps import make_cluster_api
from tools.steps import prepare_objects_with_notes
from tools.time_tools import Ago
from tools.types import BaseType
from tools.webdriver import LastRequestsContext

from pages.base_page import is_element_exist
from pages.input_base import ElementInputException
from pages.input_field import MODE_ONLY_FILLED
from pages.object_thumbnail import get_tooltip_element
from pages.object_thumbnail import is_element_inside
from pages.root import RootPage
from pages.search import template_to_filter
from pages.search.results_v2 import SearchResultPageV2

from tests_webui.regression import check_zoom
from tests_webui.regression import check_thumbnail_meta_tooltips

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.regression,
]

BIG_SERIAL_MAX = 9223372036854775807
CUSTOM_FACE_FILTERS = consts.FILTER_MALE | {consts.FILTER_AGE: (10, 50)}  # TODO: beard, mask, glasses
CUSTOM_VEHICLE_FILTERS = consts.FILTER_TRUCK | {consts.FILTER_LICENSE_PLATE: '12345'}  # TODO: manufacturer, color, model

CUSTOM_COMMON_FILTER = (
    consts.FILTER_ORDER_BY_OLD_TO_NEW |
    {consts.FILTER_START_PERIOD: Ago('-2h').dt} |
    {consts.FILTER_END_PERIOD: Ago('-1h').dt} |
    consts.FILTER_BAD_QUALITY |
    # {consts.FILTER_OBJECTS_NAME: 'test name'} |   # temporary disabled due to engine/http-api/object-management/object-manager/-/issues/352
    {consts.FILTER_OBJECTS_NOTES: 'test note'} |
    {consts.FILTER_CAMERAS_LOCATIONS: ['camera-1', 'camera-4']}
)  # filters common for all bases but with non-default values

SEARCH_RESULT_THUMBNAIL_EXPECTED_ICONS = {
    consts.BASE_FACE: [{'CAMERA', 'FACE INFO', 'OBJECT ID', 'DATETIME', 'POPUP'}],
    consts.BASE_VEHICLE: [{'POPUP', 'LICENSE PLATE', 'OBJECT ID', 'CAMERA', 'VEHICLE INFO', 'DATETIME'}],
    consts.BASE_PERSON: [
        # FYI: sometimes they disable clusterization for persons
        # TODO: adress this problem with with pytest.marks (to be able to enable/disable clusterization tests for certain base)
        {'POPUP', 'DATETIME', 'OBJECT ID', 'CAMERA', 'FACE INFO'},
    ],
}
for _base, _icons in SEARCH_RESULT_THUMBNAIL_EXPECTED_ICONS.items():
    if _base != 'face':
        continue
    _icons_with_eye = _icons[0].copy()
    _icons_with_eye.add('EYE')
    _icons.append(_icons_with_eye)


PREDICATE_NEW_TO_OLD = lambda thumbs, ix: thumbs[ix].to_datetime() >= thumbs[ix+1].to_datetime()
PREDICATE_OLD_TO_NEW = lambda thumbs, ix: thumbs[ix].to_datetime() <= thumbs[ix+1].to_datetime()


def get_search_results_screenshot(results: SearchResultPageV2):
    # move mouse pointer out from action buttons
    # since action button tooltip may fail screenshot comparison check
    action_buttons_element = results.get_object(results.x_root_action_buttons)
    results._action_chains.move_to_element_with_offset(action_buttons_element, xoffset=0, yoffset=-10).perform()

    return results._cards_container.screenshot_as_png


def check_thumbs_are_sorted_by_time(results, predicate):
    thumbs = results.thumbs
    for ix in range(len(thumbs)-1):
        assert predicate(thumbs, ix)


def merge_dict_values(*dicts):
    new_dict = {}
    d0, *other_dicts = dicts
    for key in d0:
        new_dict[key] = [d0[key]]
        for another_dict in other_dicts:
            new_dict[key].append(another_dict[key])
    return new_dict


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to resize images in search results")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1241')
@pytest.mark.usefixtures('teardown_restore_default_zoom_in_search')
def test_v2_search_resize(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    results = metapix.search('face', fetch_more=False)
    check_zoom(results, check_state_persistence=True)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Check multiselect works")
@pytest.mark.skip('Multiselect is disabled at moment')
@pytest.mark.parametrize(
    'templates',
    (
        ('vehicle-color-black', 'vehicle-color-blue'),
    ),
)
def test_v2_search_multiselect_works(metapix, sender, templates):
    sender.check_min_objects_count(
        {
            'vehicle-type-sedan': 1,
            'vehicle-type-truck': 1,
            'vehicle-color-black': 1,
            'vehicle-color-blue': 1,
        },
        timeslice=None,
    )
    search_panel = metapix.open_search_panel().\
        set_search_objective('vehicle')

    filters = merge_dict_values(*[template_to_filter(template) for template in templates])
    filter_name = tuple(filters.keys())[0]
    filters = filters[filter_name]
    control = search_panel.init_control(filter_name)

    control.select_option(filters)
    assert control.value == ', '.join(filters)

    results = search_panel.get_results()
    expected_objects_count = 0
    for template in templates:
        expected_objects_count += sender.objects_count(template, timeslice=None)
    assert results.objects_count == expected_objects_count


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible clear ordering for {base}")
@pytest.mark.parametrize('base', ['face'])
def test_v2_search_clear_order_by_filter(metapix, base):
    with allure.step('Do not perform search before clearing "Order By" field'):
        search_panel = metapix.open_search_panel(). \
            set_search_objective(base)
        search_panel.set_filters(consts.FILTER_ORDER_BY_OLD_TO_NEW)
        search_panel.select_order_results.clear_with_button()
        assert search_panel.sort_method == consts.ORDER_NEW_TO_OLD
        check_thumbs_are_sorted_by_time(search_panel.get_results(), PREDICATE_NEW_TO_OLD)

    with allure.step('Perform search before clearing "Order By" field'):
        search_panel = metapix.open_search_panel()
        search_panel.set_filters(consts.FILTER_ORDER_BY_OLD_TO_NEW)
        search_panel.get_results()
        search_panel = metapix.open_search_panel()
        search_panel.select_order_results.clear_with_button()
        assert search_panel.sort_method == consts.ORDER_NEW_TO_OLD
        check_thumbs_are_sorted_by_time(search_panel.get_results(), PREDICATE_NEW_TO_OLD)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible clear object filters for {base}")
@pytest.mark.parametrize(
    'base,filters',
    (
        # TODO: seperate test for camera/location
        # TODO: seperate test for time interval
        # TODO: seperate test for cluster name
        # TODO: seperate test for object notes
        ['face', consts.FILTER_MALE],
        ['vehicle', consts.FILTER_HATCHBACK],
    ),
    ids=['face', 'vehicle'],
)
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/991")
def test_v2_search_clear_object_filters_with_search(metapix, sender, base, filters):
    sender.check_min_objects_count(
        {
            'vehicle-type-hatchback': 1,
            'vehicle-type-sedan': 1,
            'vehicle-color-black': 1,
            'face-female': 1,
            # 'face-with-mask': 1,
            'face-with-glasses': 1,
            'face-with-beard': 1,
        },
        timeslice=None,
    )
    search_panel = metapix.open_search_panel().\
        set_search_objective(base)
    search_panel.set_filters(filters)
    search_panel.get_results()
    search_panel = metapix.open_search_panel()

    for filter_name, actual_value in filters.items():
        control = search_panel.init_control(filter_name)
        assert control.value == actual_value  # self check

        control.clear_with_button()
        assert control.value == control.default_value

    results = search_panel.get_results()
    assert results.objects_count == sender.objects_count(base, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("Eye icon not shown in thumbnail of object with cluster size 1")
@pytest.mark.parametrize("base", ['face', 'vehicle'])
def test_v2_search_eye_not_shown_for_single_object(metapix, sender, base):
    sender.check_min_objects_count(
        {
            'face-with-glasses': 1,
            'face-with-beard': 1,
            # 'face-with-mask': 1,
            'vehicle-type-unknown': 1,
            'vehicle-type-minivan': 1,
        },
        timeslice=None,
    )
    with allure.step('Try to find an object without cluster'):
        obj = get_objects_without_cluster(sender.client, base).get_first()
        card = metapix.search(base). \
            find(lambda t: t.id == obj.id).get_first()

    assert "EYE" not in card.icons_schema


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("[V2] White eye icon on a matched object's card, yellow icon on the reference object card ({object_type})")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/285')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1353')
@pytest.mark.parametrize('object_type', [
    pytest.param('face-female', marks=[pytest.mark.clusterization_faces]),
])
def test_v2_search_color_eye_icon_in_clusterized_objects(metapix, object_type, sender):
    # TODO: refactoring is required
    make_cluster_api(sender, object_type, timeslice=None)
    results_page = metapix.search(object_type)
    results_ref_count = 0
    for thumnail in results_page.thumbs[:3]:
        is_reference = False
        if not thumnail.has_eye():
            continue
        if thumnail.is_head_of_cluster():
            results_ref_count += 1
            is_reference = True
        object_card = thumnail.open_card()
        object_card.similar_objects_grid.fetch_more()
        assert is_reference == object_card.thumbnail.is_head_of_cluster()
        object_card_ref_count = 0
        for sim_obj in object_card.similar_objects:
            if not sim_obj.has_eye():
                continue
            if sim_obj.is_head_of_cluster():
                object_card_ref_count += 1
        assert object_card_ref_count == 1
        object_card.back()
    assert results_ref_count > 0, "There is no reference card"


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Filter by camera/location in advanced search")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_v2_search_filter_by_camera_location(sender, metapix):
    create_location_schema_api(sender.client, {
        "loc-1": ["camera-1", "camera-3"],
        "loc-2": ["camera-2"],
    })
    # lets don't use camera-4. but we should consider this camera
    sender.check_diff_objects_count_in_cameras(
        'face', 'camera-1', 'camera-2', 'camera-3', timeslice=None)

    search_panel = metapix.open_search_panel().set_search_objective("face")
    assert search_panel.filtered_by == 'Filtered by: 4 Cameras'

    search_panel.set_filters(cameras=['camera-4'], locations=['loc-1'])
    assert search_panel.filtered_by == 'Filtered by: 3 Cameras'
    search_results = search_panel.get_results()
    assert sender.objects_count("face", cameras=['camera-1', 'camera-3', 'camera-4'], timeslice=None) ==  \
        search_results.objects_count

    # check info about filtered cameras has been kept
    search_panel = metapix.open_search_panel().set_search_objective("face")
    assert search_panel.filtered_by == 'Filtered by: 3 Cameras'

    search_panel.set_filters(locations=['loc-2'])
    assert search_panel.filtered_by == 'Filtered by: 1 Camera'
    search_results = search_panel.get_results()
    assert sender.objects_count("face", cameras='camera-2', timeslice=None) == search_results.objects_count


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Testing search with object notes for {base}")
@pytest.mark.usefixtures('teardown_delete_object_notes')
@pytest.mark.parametrize('base', ['face', 'vehicle'])
def test_v2_search_with_objects_notes(metapix, sender, base):
    obj = search_api_v2(sender.client, base).get_first()
    change_object_notes(sender.client, obj, 'Test note')

    assert metapix.search_count(base, {consts.FILTER_OBJECTS_NOTES: 'Test note'}) == 1


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It is possible to search faces by gender")
@pytest.mark.parametrize("filters,meta", [
    (consts.FILTER_MALE, consts.META_MALE),
    (consts.FILTER_FEMALE, consts.META_FEMALE),
], ids=['male', 'female'])
def test_v2_search_face_filter_gender(metapix, sender, filters, meta):
    sender.check_diff_objects_count(consts.FACE_GENDERS, timeslice=None)
    assert metapix.search_count("face", filters) == sender.objects_count("face", meta, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: test location filter for {base}")
@pytest.mark.parametrize("base", ["face", "vehicle", "person"])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_v2_search_filtering_by_locations(metapix, sender, base):
    # TODO: use accumulative logic
    # TODO: use templates instead of base (to prevent overflows)
    loc_schema = {
        "loc-1": ["camera-1", "camera-3"],
        "loc-2": ["camera-2"],
    }
    sender.check_diff_objects_count_in_cameras(
        base, loc_schema["loc-1"], loc_schema["loc-2"], timeslice=None)
    create_location_schema_api(sender.client, loc_schema)

    for location in loc_schema:
        results_page = metapix.search(base, {"locations": [location]})
        assert results_page.objects_count == sender.objects_count(base, cameras=loc_schema[location], timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search with empty location")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_v2_search_filtering_by_empty_locations(metapix, sender):
    sender.check_diff_objects_count_in_cameras(
        "face", "camera-1", "camera-2", "camera-3", timeslice=None)
    create_location_schema_api(sender.client, {"loc-empty": []})

    filter_dialog = metapix.open_search_panel(). \
        set_search_objective('face'). \
        open_camera_picker()
    check_filtering_with_empty_location(filter_dialog, 'loc-empty')


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It is possible to sort search results by arrival time")
@pytest.mark.parametrize('base', ['vehicle'])
def test_v2_search_sort_by_arrival_time(metapix, sender, base):
    sender.check_min_objects_count({base: 3}, timeslice=None)

    # "New To Old" by default
    check_thumbs_are_sorted_by_time(
        metapix.search(base, fetch_more=False),
        PREDICATE_NEW_TO_OLD,
    )

    check_thumbs_are_sorted_by_time(
        metapix.search(base, filters=consts.FILTER_ORDER_BY_OLD_TO_NEW),
        PREDICATE_OLD_TO_NEW,
    )


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to set filter by image quality for {base}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/277")
@pytest.mark.parametrize("base", [consts.BASE_FACE, consts.BASE_VEHICLE, consts.BASE_PERSON])
@pytest.mark.parametrize(
    "filters,meta",
    [
        (consts.FILTER_BAD_QUALITY, consts.META_BAD_QUALITY)
    ],
    ids=['bad'],   # test for good quality has been deleted since it has no sense
)
def test_v2_search_filtering_by_img_quality(metapix, sender, base, filters, meta):
    sender.check_diff_objects_count([f"{base}-bad-quality", f"{base}-good-quality"], timeslice=None)

    assert metapix.search_count(base, filters) == sender.objects_count(base, meta, timeslice=None)
    assert metapix.search_count(base, consts.FILTER_ANY_QUALITY) == \
        sender.objects_count(base, consts.META_ANY_QUALITY, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search vehicle: check filtering options: manufacturer, model, color, type ({object_type})")
@pytest.mark.parametrize(
    "filters, object_type", [
        (consts.FILTER_MINIVAN, 'vehicle-type-minivan'),
    ],
    ids=[
        "type",  # TODO: add manufacturer, model, color
    ]
)
def test_v2_search_vehicle_dropdown_filters(metapix, sender, filters, object_type):
    sender.check_diff_objects_count([
        'vehicle-type-sedan',
        'vehicle-type-minivan',
    ], timeslice=None)
    assert metapix.search_count('vehicle', filters) == sender.objects_count(object_type, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to set filter by age for Faces")
@pytest.mark.parametrize("ages", [(20, 49), (50, 99)], ids=["young", "old"])
def test_v2_search_face_filter_age(metapix, sender, ages):
    sender.check_diff_objects_count(["face-50-age", "face-30-age"], timeslice=None)

    assert metapix.search_count("face", {consts.FILTER_AGE: ages}) == \
        sender.objects_count_for_ages(timeslice=None, *ages)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to apply 'Date from' and 'Date to' filters")
@pytest.mark.parametrize(
    'base,date_1,date_2',
    [
        ('face', Ago('-2d'), Ago('-1d')),
        ('vehicle', Ago('-10m'), Ago('-5m')),
    ],
    ids=['face-2d-1d', 'vehicle-10m-5m'],
)
def test_v2_search_filtering_by_date(metapix, sender, base, date_1, date_2):
    '''
    long_time_ago .......... date_1 .... date_2 .... time_now
                               ^           ^
                               |           |
                            -2 days     -1 days
    '''
    def clear_and_get_results(filters, *to_clear):
        for control_name in to_clear:
            getattr(filters, control_name).clear_with_button()
        return filters.get_results().objects_count

    sender.objects_count_in_interval(base, None, date_1, min_objects_count=1)
    sender.objects_count_in_interval(base, date_1, date_2, min_objects_count=1)
    sender.objects_count_in_interval(base, date_2, None, min_objects_count=1)

    # date_1 .. date_2
    results = metapix.search(base, date_from=date_1.dt, date_to=date_2.dt)
    search_panel = metapix.open_search_panel()
    assert results.objects_count == sender.objects_count_in_interval(base, date_1, date_2)

    # None .. date_2
    assert clear_and_get_results(search_panel, 'date_from') == \
        sender.objects_count_in_interval(base, None, date_2)

    # date_1 .. now
    search_panel.set_filters(date_from=date_1.dt)
    assert clear_and_get_results(search_panel, 'date_to') == \
        sender.objects_count_in_interval(base, date_1, None)

    # None .. now (all objects)
    assert clear_and_get_results(search_panel, 'date_from') == \
        sender.objects_count(base, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to set filter by glasses, mask and beard")
# @pytest.mark.parametrize(
#     "attribute,meta_with,meta_without",
#     [
#         (consts.FILTER_GLASSES, consts.META_WITH_GLASSES, consts.META_WITHOUT_GLASSES),
#         pytest.param(
#             consts.FILTER_MASK, consts.META_WITH_MASK, consts.META_WITHOUT_MASK,
#             marks=allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/whole-project-tasks/-/issues/145'),
#         ),
#         (consts.FILTER_BEARD, consts.META_WITH_BEARD, consts.META_WITHOUT_BEARD),
#     ],
#     ids=["glasses", "mask", "beard"],
# )
@pytest.mark.skip('Glasses/beard/mask analytics are temporary disabled (http-api/object-management/object-manager/-/issues/309)')
def test_v2_search_face_filters_with_without(metapix, sender, attribute, meta_with, meta_without):
    sender.check_diff_objects_count(
        ["face-with-glasses", "face-with-beard", "face-with-mask"], timeslice=None)

    assert metapix.search_count("face", {attribute: consts.OPTION_WITH}) == \
        sender.objects_count("face", meta_with, timeslice=None)
    assert metapix.search_count("face", {attribute: consts.OPTION_WITHOUT}) == \
        sender.objects_count("face", meta_without, timeslice=None)
    assert metapix.search_count("face", {attribute: consts.OPTION_ALL}) == \
        sender.objects_count("face", timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: check 'Not empty' checkboxes work for several object names")
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.parametrize('count', [4])
def test_v2_search_not_empty_checkboxes_several_object_names(metapix, sender, count):
    objects = get_suitable_objects(
        sender,
        ['vehicle'],
        allow_single_objects=True,
        count=count,
        min_cluster_size=1,
        max_cluster_size=1,
    )
    for ix, obj in enumerate(objects):
        change_cluster_name(sender.client, obj, f'cluster {ix}')

    search_panel = metapix.open_search_panel().set_search_objective('vehicle')
    search_panel.input_object_name.select_only_filled_mode()
    results = search_panel.get_results()
    assert results.objects_count == count


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: check 'Not empty' checkboxes work for cluster")
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.clusterization_faces
def test_v2_search_not_empty_checkboxes_for_cluster(metapix, sender):
    cluster = make_cluster_api(sender, 'face-male', timeslice=None)
    change_cluster_name(sender.client, cluster, 'Test name')

    search_panel = metapix.open_search_panel().set_search_objective('face')
    search_panel.input_object_name.select_only_filled_mode()
    results = search_panel.get_results()
    assert results.objects_count == cluster.cluster_size


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: check 'Not empty' checkboxes work for object notes for {base}")
@pytest.mark.usefixtures('teardown_delete_object_notes')
@pytest.mark.parametrize(
    "base,notes_count",
    [
        ("vehicle", 3),
        ("face", 4),
    ],
    ids=['vehicle', 'face'],
)
def test_v2_search_not_empty_checkboxes_object_notes(metapix, sender, base, notes_count):
    prepare_objects_with_notes(sender, base, notes_count)

    search_panel = metapix.open_search_panel().set_search_objective(base)
    search_panel.input_object_note.select_only_filled_mode()
    results = search_panel.get_results()
    assert results.objects_count == notes_count


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: check 'Not empty' checkboxes work for license plate")
def test_v2_search_not_empty_checkbox_license_plate(metapix, sender):
    sender.check_min_objects_count({"vehicle": 1}, meta=consts.META_LIC_PLATE_12345)

    search_panel = metapix.open_search_panel(). \
        set_search_objective("vehicle")
    search_panel.input_license_plate.select_only_filled_mode()
    results = search_panel.get_results()
    assert results.objects_count == sender.objects_count("vehicle", meta={consts.META_LIC_PLATE: '*'}, timeslice=None)

    card = results.find(lambda t: t.license_plate == '12345').get_first()
    popup = card.open_card().thumbnail.open_popup()
    assert '12345' in popup.license_plate


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to set filter by license plate for Vehicles")
def test_v2_search_filter_license_plate(metapix, sender):
    sender.check_min_objects_count({"vehicle": 1}, meta=consts.META_LIC_PLATE_12345)
    search = metapix.open_search_panel(). \
        set_search_objective('vehicle')
    results = search.set_license_plate("*"). \
        get_results()

    assert results.objects_count == sender.objects_count(
        "vehicle", meta={consts.META_LIC_PLATE: '*'}, timeslice=None)
    card = results.find(lambda t: t.license_plate == '12345').get_first()
    popup = card.open_card().thumbnail.open_popup()
    assert '12345' in popup.license_plate


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("[V2] Testing search with object name")
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.clusterization_faces
def test_v2_search_with_cluster_name(metapix, sender):
    obj = make_cluster_api(sender, 'face-female', timeslice=None, min_cluster_size=5)
    change_cluster_name(sender.client, obj, 'Test name')

    assert metapix.search_count('face', {consts.FILTER_OBJECTS_NAME: 'Test name'}) == obj.cluster_size


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("[V2] Testing search with several object names")
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.parametrize('count', [4])
def test_v2_search_with_several_object_names(metapix, sender, count):
    objects = get_suitable_objects(
        sender,
        ['vehicle'],
        allow_single_objects=True,
        count=count,
        min_cluster_size=1,
        max_cluster_size=1,
    )
    for ix, obj in enumerate(objects):
        change_cluster_name(sender.client, obj, f'cluster {ix}')

    assert metapix.search_count('vehicle', {consts.FILTER_OBJECTS_NAME: '*'}) == count
    metapix.open_search_panel(). \
        input_object_name.select_specific_name_mode()
    results = metapix.search('vehicle', {consts.FILTER_OBJECTS_NAME: obj.meta['name']})
    assert results.objects_count == 1
    assert results.thumbs[0].id == obj.id


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("[V2] Search result: base changes after refresh, no objects")
def test_v2_search_result_base_changed_after_refresh(metapix, sender):
    # TODO: change scenario if issued would fixed
    sender.check_diff_objects_count(["person", "face", "vehicle"], timeslice=None)

    results = metapix.search('person', fetch_more=True)

    # TODO: explicitly check object types
    assert results.objects_count == sender.objects_count("person", timeslice=None)
    metapix.refresh()
    results.fetch_more()
    assert results.objects_count == sender.objects_count("person", timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("Icons should be correctly displayed in object's card in search results for {object_type}")
@pytest.mark.parametrize('object_type', [
    pytest.param('face-female', marks=pytest.mark.clusterization_faces),
])
def test_search_thumbnail_icons(sender, metapix, object_type):
    base = parse_object_type(object_type)[0]
    make_cluster_api(sender, object_type, timeslice=None)

    thumbnail = find_card_with_eye(metapix.search(object_type))
    with allure.step(f'Check icons for {thumbnail}'):
        assert thumbnail.icons_schema in SEARCH_RESULT_THUMBNAIL_EXPECTED_ICONS[base]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible clear datetime filter")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/954")
def test_v2_search_clear_datetime_filters(metapix):
    search_panel = metapix.open_search_panel().\
        set_search_objective('face')
    search_panel.set_date_filter(Ago('-1h').dt, Ago(0).dt)

    with allure.step('Check clear button work for "date from"'):
        search_panel.date_from.clear_with_button()
        assert search_panel.date_from.value == ''

    with allure.step('Check clear button work for "date to"'):
        search_panel.date_to.clear_with_button()
        assert search_panel.date_to.value == ''


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/981")
@allure.title("[V2] Selected cameras and locations shouldn't be kept after switching base")
def test_v2_search_selected_cameras_after_switch_base(metapix):
    search_panel = metapix.open_search_panel().set_search_objective('face')
    search_panel.set_filters(cameras=['camera-2'])

    with allure.step('Check no cameras/locations are selected after switching base'):
        for tab in ('vehicle', 'person'):
            search_panel.set_search_objective(tab)
            assert search_panel.filtered_by == 'Filtered by: 4 Cameras'
            filter_dialog = search_panel.open_camera_picker()
            assert filter_dialog.schema == ['camera-1 ☑', 'camera-2 ☑', 'camera-3 ☑', 'camera-4 ☑']
            filter_dialog.apply()


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("Caption with selected cameras/locations always have to be displayed")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1027")
@pytest.mark.parametrize('base', ['face'])
def test_filter_by_cameras_location_label_disappear(metapix, base):
    search_panel = metapix.open_search_panel().set_search_objective(base)
    filter_dialog = search_panel.open_camera_picker()
    assert filter_dialog.label_selected_text == 'Information\nYou have selected 4 cameras'

    filter_dialog.set_filters(cameras=['camera-2'])
    with allure.step('Check there is caption with amount of selected entities'):
        assert filter_dialog.label_selected_text == 'Information\nYou have selected 1 camera'


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("[v2] 'Camera/location' and 'datetime' filters shouldn't be reseted after choosing another filters for {base}")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/970")
@pytest.mark.parametrize('base,filters', [('vehicle', CUSTOM_VEHICLE_FILTERS)])
def test_v2_search_cameras_location_and_datetime_filters_resets(metapix, base, filters):
    filters = filters | CUSTOM_COMMON_FILTER
    del filters[consts.FILTER_START_PERIOD]
    del filters[consts.FILTER_END_PERIOD]
    del filters[consts.FILTER_CAMERAS_LOCATIONS]
    search_panel = metapix.open_search_panel().set_search_objective(base)
    search_panel.set_date_filter(Ago('-1h').dt, Ago(0).dt)
    expected_date_from, expected_date_to = search_panel.date_from.value, search_panel.date_to.value
    assert expected_date_from and expected_date_to
    search_panel.set_filters(cameras=['camera-2', 'camera-4'])
    expected_selected_cameras = search_panel.filtered_by
    assert expected_selected_cameras == 'Filtered by: 2 Cameras'
    search_panel.set_filters(filters)

    with allure.step('Check camera/location and datetime filters have not been changed'):
        assert search_panel.filtered_by == expected_selected_cameras
        assert search_panel.date_from.value == expected_date_from
        assert search_panel.date_to.value == expected_date_to
        filter_dialog = search_panel.open_camera_picker()
        assert filter_dialog.schema == ['camera-1 ☐', 'camera-2 ☑', 'camera-3 ☐', 'camera-4 ☑']


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("[v2] multiselect dropdowns shouldn't change their width or position if several options have been selected")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/968")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/969")
@pytest.mark.skip('Multiselect is disabled at moment')
def test_v2_search_multiselect_dropdown_changes_size_or_location(metapix):
    search_panel = metapix. \
        open_search_panel(). \
        set_search_objective('vehicle')
    control = search_panel.init_control(consts.FILTER_COLOR)
    expected_control_size = control.root.size

    control.expand()
    expected_size = control.dropdown_element.size
    expected_location = control.dropdown_element.location

    control._select_option(['Black', 'Blue', 'Brown', 'Green', 'Red'])
    with allure.step('Check dropdown rectangle has not changed'):
        assert control.dropdown_element.size == expected_size
        assert control.dropdown_element.location == expected_location

    control.collapse()
    with allure.step('Check control size has not changed'):
        assert control.root.size == expected_control_size


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.tag('bug')
@allure.title('[v2] Check "date from" always lower than "date to"')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/955')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1228')
def test_v2_search_time_crossing(metapix):
    search_panel = metapix.open_search_panel(). \
        set_search_objective('vehicle')
    search_panel.set_date_filter(
        date_from=Ago('-1h').dt,
        date_to=Ago('-2h').dt,
    )

    with allure.step('Check date_to is upper than date_from'):
        assert search_panel.date_to.to_datetime() > search_panel.date_from.to_datetime()


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("[v2] Check filters hasn't been changed after cliking 'search' button ({base})")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/990")
@pytest.mark.parametrize(
    'base,filters',
    [
        ('face', CUSTOM_FACE_FILTERS),
        ('vehicle', CUSTOM_VEHICLE_FILTERS),
    ]
)
def test_v2_search_quality_filter_resets_after_clicking_search_button(metapix, base, filters):
    # TODO: support face + vehicle
    search_panel = metapix. \
        open_search_panel(). \
        set_search_objective(base)
    search_panel.set_filters(filters | CUSTOM_COMMON_FILTER)
    expected_filters = search_panel.filters_schema

    search_panel.get_results(ignore_no_data=True)
    with allure.step('Check filters has not changed after cliking "Search" button'):
        assert search_panel.filters_schema == expected_filters


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("[v2] It is not possible to edit 'Only filled' input after search")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/971")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/965")
def test_v2_search_check_only_filled_inputs_not_editable(metapix):
    def check(control, init_required=False):
        if init_required:
            control.select_only_filled_mode()
        with allure.step(f'{control} check is not editable'):
            with pytest.raises(ElementInputException):
                control.clear_with_keyboard()
            control.type_text("hello")
            assert control.value.lower() == MODE_ONLY_FILLED.lower()

    search_panel = metapix. \
        open_search_panel(). \
        set_search_objective('vehicle')

    check(search_panel.input_object_name, init_required=True)
    check(search_panel.input_object_note, init_required=True)
    check(search_panel.input_license_plate, init_required=True)

    search_panel.get_results(ignore_no_data=True)
    search_panel = metapix.open_search_panel()

    check(search_panel.input_object_name)
    check(search_panel.input_object_note)
    check(search_panel.input_license_plate)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/972")
@allure.title("[v2] 'Cluster name' and 'Object details' shouldn't be kept during switching between bases")
def test_v2_search_cluster_name_and_object_details_after_switch_base(metapix):
    # TODO: it is possible to merge this test with `test_v2_search_selected_cameras_after_switch_base` ??
    def check_name_and_note(panel, name, note):
        with allure.step('Check object name and note values'):
            assert panel.input_object_name.value == name
            assert panel.input_object_note.value == note

    search_panel = metapix.open_search_panel().set_search_objective('face')
    search_panel.set_object_name('hello')
    search_panel.set_object_note('world')

    search_panel = search_panel.get_results(ignore_no_data=True). \
        filters_panel

    check_name_and_note(search_panel, 'hello', 'world')
    search_panel.set_search_objective('vehicle')
    check_name_and_note(search_panel, '', '')
    search_panel.set_search_objective('person')
    check_name_and_note(search_panel, '', '')


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[v2] It is possible to hide object information on object cards")
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_restore_show_object_information')
def test_v2_search_hide_object_info(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    results = metapix.search(base)
    card = results.thumbs[0]

    with allure.step('Meta info is being shown by default'):
        assert card.meta_text

    with allure.step('Hiding meta works'):
        results.hide_object_info()
        assert not card.meta_text

    with allure.step('Hiding meta persist after refreshing page'):
        results.refresh()
        assert not card.meta_text

    with allure.step('Showing meta works'):
        results.show_object_info()
        assert card.meta_text

    with allure.step('Showing meta persist after refreshing page'):
        results.refresh()
        assert card.meta_text


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1097')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1487')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1500')
@allure.title('[V2] Search filters and objects are not available to another company for {base}')
@pytest.mark.parametrize(
    'base, filters',
    [
        ('face', CUSTOM_FACE_FILTERS),
        ('vehicle', CUSTOM_VEHICLE_FILTERS),
    ],
    ids=['face', 'vehicle'],
)
def test_v2_search_filters_not_available_for_another_company(metapix, second_company, base, filters):
    # TODO: implement second scenario (login as another user)
    def _normalize(filters):
        filters = filters.copy()
        del filters[consts.FILTER_CAMERAS_LOCATIONS]  # i suggest it is ok if another company has different amount of cameras
        return filters

    with allure.step('Get default filters'):
        panel = metapix.open_search_panel(). \
            set_search_objective(base)
        default_filters = panel.filters_schema
        panel.close()

    with allure.step('Set custom filters'):
        panel = metapix.open_search_panel(). \
            set_search_objective(base)
        panel.set_filters(filters | CUSTOM_COMMON_FILTER)
        panel.get_results(ignore_no_data=True)  # it is necessary to reproduce the bug

    with allure.step('Switch to another company and check filters'):
        metapix.switch_company(). \
            select_by_name(second_company.name)
        panel = metapix.open_search_panel(). \
            set_search_objective(base)
        assert _normalize(panel.filters_schema) == _normalize(default_filters)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: Check 'Clear filters' button works for {base}")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1123')
@pytest.mark.parametrize(
    'base, filters',
    [
        ('vehicle', CUSTOM_VEHICLE_FILTERS),
        ('face', CUSTOM_FACE_FILTERS),
    ],
    ids=['vehicle', 'face'],
)
def test_v2_search_clear_filters_button(metapix, base, sender, filters):
    '''
    "Clear filters" button at the bottom of search panel
    This test doesn't concern clearing filters with X (crosshair) in every filter field
    '''
    sender.check_diff_objects_count_in_cameras(base, 'camera-1', 'camera-2', timeslice=None)
    # don't refresh filters in another company???
    panel = metapix.open_search_panel(). \
        set_search_objective(base)
    default_filters = panel.filters_schema

    with allure.step('Right panel: "Clear filters" set up default values'):
        panel.set_filters(filters | CUSTOM_COMMON_FILTER)
        panel.clear_filters()
        assert panel.filters_schema == default_filters

    with allure.step('Left panel: "Clear filters" set up default values'):
        panel.set_filters(filters | CUSTOM_COMMON_FILTER)
        results = panel.get_results(ignore_no_data=True)
        assert results.filters_panel.filters_schema != default_filters
        results.filters_panel.clear_filters()
        assert results.filters_panel.filters_schema == default_filters

        with allure.step('Check search results corresponds to default values of filters'):
            results.filters_panel.get_results(ignore_no_data=True)
            assert results.filters_panel.filters_schema == default_filters
            assert results.objects_count == sender.objects_count(base, timeslice=None)

    with allure.step('Left + Right panel: check there are still default values after refresh'):
        results.refresh()
        results.fetch_more()
        assert results.filters_panel.filters_schema == default_filters
        assert results.objects_count == sender.objects_count(base, timeslice=None)
        panel = metapix.open_search_panel()
        assert panel.filters_schema == default_filters


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Search: Left panel equal to right after any search {base1} -> {base2}")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/985')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1173')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/305')
@pytest.mark.parametrize(
    'base1,filters1,base2,filters2', [
        ('vehicle', CUSTOM_VEHICLE_FILTERS, 'face', CUSTOM_FACE_FILTERS),
        ('face', CUSTOM_FACE_FILTERS, 'person', {}),
    ],
    ids=['vehicle-face', 'face-person'],
)
def test_v2_search_left_and_right_panel_sync(metapix, base1, filters1, base2, filters2):
    # TODO: support cameras
    with allure.step('Right panel -> Left panel sync'):
        search_panel = metapix.open_search_panel(). \
            set_search_objective(base1)
        search_panel.set_filters(filters1 | CUSTOM_COMMON_FILTER | consts.FILTER_ANY_QUALITY)
        expected_schema = search_panel.filters_schema

        left_search_panel = search_panel.get_results(ignore_no_data=True).filters_panel
        assert left_search_panel.filters_schema == expected_schema
        assert left_search_panel.current_base == base1

    with allure.step('Left panel -> Right panel sync'):
        left_search_panel.set_search_objective(base2)
        left_search_panel.set_filters(filters2 | CUSTOM_COMMON_FILTER | consts.FILTER_BAD_QUALITY)
        expected_filters = left_search_panel.filters_schema
        left_search_panel.get_results(ignore_no_data=True)

        search_panel = metapix.open_search_panel()
        assert search_panel.filters_schema == expected_filters
        assert search_panel.current_base == base2


def get_the_biggest_cluster(objects: Iterable[ObjectData]) -> int:
    clusters = defaultdict(int)
    for obj in objects:
        if is_head_of_cluster(obj):
            clusters[obj.id] += 1
        if is_not_head_of_cluster(obj):
            clusters[obj.parent_id] += 1
    try:
        return max(clusters.values())
    except ValueError as exc:  # max() iterable argument is empty
        raise RuntimeError('No clusters have been found') from exc


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("Check clusterization on lange cluster")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/285")
def test_clusterization_big_cluster(sender):
    objects = sender.send_from_dir('cluster_images/51/', 'face')
    biggest_cluster_size = get_the_biggest_cluster(objects)
    with allure.step(f'Check the biggest cluster size {biggest_cluster_size} vs objects count {len(objects)}'):
        log.info(f'Check the biggest cluster size {biggest_cluster_size} vs objects count {len(objects)}')
        assert biggest_cluster_size / len(objects) > 0.8


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] Filters on left side should reset after push clear filters button and search")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1231")
def test_v2_filters_search_should_clear_after_push_button(metapix):
    search_panel = metapix.open_search_panel()
    default_filters_schema = search_panel.filters_schema

    with allure.step('Open search panel, set filters, perform search'):
        search_panel. \
            set_filters(CUSTOM_COMMON_FILTER | CUSTOM_FACE_FILTERS)
        custom_filters_schema = search_panel.filters_schema
        search_panel.get_results(ignore_no_data=True, fetch_more=False)

    with allure.step('Open search panel again, clear filters, perform search'):
        metapix. \
            open_search_panel()
        assert search_panel.filters_schema == custom_filters_schema
        search_panel. \
            clear_filters(). \
            get_results(ignore_no_data=True, fetch_more=False)

    with allure.step('Check left panel filters'):
        assert metapix.open_search_panel().filters_schema == default_filters_schema


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.tag('bug')
@allure.title('Tooltip is shown in wrong place after zooming out')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1300')
@pytest.mark.clusterization_faces
@pytest.mark.usefixtures('teardown_restore_default_zoom_in_search')
def test_v2_search_tooltip_is_in_wrong_place_after_zoom_out(metapix, sender):
    make_cluster_api(sender, 'face-male', timeslice=None)
    results = metapix.search('face', fetch_more=False)
    thumbs_with_eye = [thumb for thumb in results.thumbs if is_element_exist(lambda: thumb._eye)]
    if not thumbs_with_eye:
        raise PreconditionException('No objects with eye')
    results.zoom_out(times=5)
    thumbnail = thumbs_with_eye[0]
    assert is_element_inside(get_tooltip_element(thumbnail, thumbnail.button_popup), thumbnail.root)
    assert is_element_inside(get_tooltip_element(thumbnail, thumbnail._eye), thumbnail.root)


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Search by Object ID: check input has clear button')
@pytest.mark.parametrize('base', ['face'])
def test_v2_search_identifier_field_has_clear_button(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    search_panel = metapix.open_search_panel(). \
        set_search_objective(consts.SEARCH_OBJECTIVE_ID)
    obj = search_api_v2(sender.client, base).get_first()

    search_panel.input_object_id.type_text(obj.id)
    search_panel.input_object_id.clear_with_button()
    assert search_panel.input_object_id.value == ''


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Search by Object ID: look for non existing object')
@pytest.mark.parametrize('non_existing_id', ['123'])
def test_v2_search_non_existing_identifier(metapix, non_existing_id):
    ''' FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1410#note_73006 '''
    search_panel = metapix.open_search_panel()
    results = search_panel.set_filters({
        consts.FILTER_SEARCH_OBJECTIVE: consts.SEARCH_OBJECTIVE_ID,
        consts.FILTER_OBJECT_ID: non_existing_id
    }). \
        get_results(ignore_no_data=True)
    # TODO: check "No data" message
    assert results.objects_count == 0


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Search by Object ID: clear filters')
@pytest.mark.parametrize('base', ['face'])
def test_v2_search_identifier_clear_filters(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    obj = search_api_v2(sender.client, base).get_first()
    default_filters = {
        consts.FILTER_SEARCH_OBJECTIVE: consts.SEARCH_OBJECTIVE_ID,
        consts.FILTER_OBJECT_ID: '',
    }
    object_id_filter = {consts.FILTER_OBJECT_ID: str(obj.id)}
    search_panel = metapix.open_search_panel()
    search_panel.set_filters(default_filters | object_id_filter). \
        get_results(ignore_no_data=False)
    assert search_panel.filters_schema == default_filters | object_id_filter

    search_panel.clear_filters()
    assert search_panel.filters_schema == default_filters


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Search by Object ID: input validation (use left pane: {use_left_panel})')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1507')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1582')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize('use_left_panel', [True, False], ids=['left_panel', 'right_panel'])
def test_v2_search_identifier_field_validation(
        metapix: RootPage, sender: ImageSender, base: BaseType, use_left_panel: bool):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    search_panel = metapix.open_search_panel()
    if use_left_panel:
        search_panel.get_results(ignore_no_data=True, fetch_more=False)
    search_panel.set_search_objective(consts.SEARCH_OBJECTIVE_ID)
    obj = search_api_v2(sender.client, base).get_first()

    check_input_validation(
        control=search_panel.input_object_id,
        valid=[
            obj.id,
            str(BIG_SERIAL_MAX - 10),
        ],
        invalid=[
            '',
            'fffff',
            str(BIG_SERIAL_MAX + 10),  # https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/423
                                       # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1575
        ],
        button=search_panel.button_search,
    )


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Scale of pictures changes when clicking on the SCALE strip')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1134')
@pytest.mark.usefixtures('teardown_restore_default_zoom_in_search')
def test_resize_by_clicking_on_scale_strip(metapix, sender):
    # TODO: more scenarios
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    results = metapix.search('face', fetch_more=False)
    state_before = get_search_results_screenshot(results)
    results.scale_at(0.25)
    check_images_are_not_equal(state_before, get_search_results_screenshot(results))


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('[V2] It should be possible to resize images in search results')
@pytest.mark.usefixtures('teardown_restore_default_zoom_in_search')
def test_v2_search_resize_thumbnails(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    results = metapix.search('face', fetch_more=False)
    initial_state = get_search_results_screenshot(results)
    results.zoom_out(times=3)
    check_images_are_not_equal(initial_state, get_search_results_screenshot(results))

    results.reset_zoom()
    check_images_are_equal(initial_state, get_search_results_screenshot(results))


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('There is no extra search request while searching by id')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1511')
def test_extra_request_in_search_by_id(
        metapix: RootPage, sender: ImageSender):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({'vehicle': 1}, timeslice=None)
        obj = search_api_v2(sender.client, 'vehicle').get_first()

    with allure.step('Search object with non existing id'):
        search_panel = metapix.open_search_panel()
        search_panel.set_filters({
            consts.FILTER_SEARCH_OBJECTIVE: consts.SEARCH_OBJECTIVE_ID,
            consts.FILTER_OBJECT_ID: '1',  # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1410#note_73006
        })
        search_panel.get_results(ignore_no_data=True, ignore_error_tooltip=True)

    with allure.step('Open dashboard and then open search panel again'):
        metapix.open_dashboard()
        search_panel = metapix.open_search_panel()

    with allure.step('Look for object with existing id'):
        search_panel.set_filters({consts.FILTER_OBJECT_ID: obj.id})
        with LastRequestsContext(metapix.driver) as get_last_req_func:
            search_panel.get_results()
            requests = get_last_req_func(url='/object-manager/objects/')

    with allure.step('Check there is only one request to get object'):
        assert len(requests) == 1


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Check ROI state in search results')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1504')
@pytest.mark.parametrize('base', ['face', 'vehicle'])
@pytest.mark.usefixtures('teardown_restore_roi_state')
def test_search_roi_state(
        metapix: RootPage, sender: ImageSender, base: BaseType):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({base: 1}, timeslice=None)

    with allure.step('Check ROI state is 1 by default'):
        search_results = metapix.search(base, fetch_more=False)
        assert search_results.roi_state_number == 1
        roi1_thumbs_state = get_search_results_screenshot(search_results)

    with allure.step('Try to switch ROI state 1 -> 2'):
        search_results.switch_roi_state()
        assert search_results.roi_state_number == 2
        roi2_thumbs_state = get_search_results_screenshot(search_results)
        check_images_are_not_equal(roi1_thumbs_state, roi2_thumbs_state)

    with allure.step('Check ROI state persist after page is being refreshed'):
        search_results.refresh()
        check_images_are_equal(roi2_thumbs_state, get_search_results_screenshot(search_results))
        assert search_results.roi_state_number == 2

    if base == 'vehicle':
        # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1597
        with allure.step('Switch to ROI state 2 -> 3 (vehicles)'):
            roi2_thumbs_state = get_search_results_screenshot(search_results)
            search_results.switch_roi_state()
            assert search_results.roi_state_number == 3
            check_images_are_not_equal(roi2_thumbs_state, get_search_results_screenshot(search_results))

    with allure.step('Switch to ROI state 1'):
        search_results.switch_roi_state()
        assert search_results.roi_state_number == 1
        check_images_are_equal(roi1_thumbs_state, get_search_results_screenshot(search_results))


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1608')
@allure.title('Check tooltips for meta information in object thumbnail: search results')
@pytest.mark.parametrize('base', ['person'])
def test_object_thumb_meta_tooltips_search_results(sender: ImageSender, metapix: RootPage, base: BaseType):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({base: 1}, timeslice=None)
        search_results = metapix.search(base, fetch_more=False)

    with allure.step('Check tooltips thumnail in search results'):
        thumb = search_results.thumbs[0]
        check_thumbnail_meta_tooltips(thumb, base, get_object(sender.client, thumb.id))
