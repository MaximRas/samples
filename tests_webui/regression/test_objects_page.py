'''
FYI:
  - https://metapix-workspace.slack.com/archives/C03KBMWC146/p1692870515423259
'''
from functools import partial
import itertools
import re
import time

from tools.client import ApiClient
from tools.watchlists import create_watchlist
from tools.watchlists import add_predicates
from tools.watchlists import create_face_predicates
from typing import Sequence

import allure
import pytest

import consts
from tools import check_images_are_equal
from tools import check_images_are_not_equal
from tools import parse_object_type
from tools.image_sender import ImageSender
from tools.objects import change_cluster_name
from tools.objects import get_object
from tools.objects import get_object_with_uniq_license_plate
from tools.objects import get_objects_with_non_equal_license_plate
from tools.objects import get_objects_without_cluster
from tools.objects import get_objects_without_license_plate
from tools.objects import get_suitable_objects
from tools.search import search_api_v2
from tools.steps import check_input_validation
from tools.steps import find_clusters_api
from tools.steps import get_hover_tooltip
from tools.steps import make_cluster_api
from tools.types import BaseType
from tools.users import auth_user_in_browser
from tools.users import get_active_company
from tools.webdriver import CustomWebDriver
from tools.webdriver import LastRequestsContext

from pages.base_page import is_element_exist
from pages.dropdown import DropdownExpandException
from pages.object_card import expected_icons_card_cluster
from pages.object_card import expected_icons_card_no_cluster
from pages.object_card import expected_meta_card
from pages.object_popup_dialog import expected_popup_icons
from pages.object_popup_dialog import expected_popup_meta
from pages.object_thumbnail import ObjectThumbnail
from pages.root import RootPage
from pages.search.results_v2 import SearchResultPageV2

from tests_webui.regression import check_zoom
from tests_webui.regression import check_card_meta
from tests_webui.regression import check_thumbnail_meta_tooltips

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Check popup icons and meta for {base}")
@pytest.mark.parametrize('base', ["face", "vehicle"])
def test_object_card_popup_icons_and_meta(metapix, base, sender):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    if base == 'vehicle':
        obj = next(get_objects_without_license_plate(sender))
    if base == 'face':
        obj = search_api_v2(sender.client, 'face')[0]
    card = metapix.open_object(obj.id)
    popup_dialog = card.thumbnail.open_popup()

    assert popup_dialog.icons_schema == expected_popup_icons[base]

    check_card_meta(popup_dialog.meta_text, expected_popup_meta(card), base)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Check icons in object card for {base}")
@pytest.mark.parametrize("base", ['face', 'vehicle', 'person'])
def test_object_card_icons(sender, metapix, base):
    '''
    Lets not consider this test as 'clusterization' test since we don't need any cluster actually
    '''
    sender.check_min_objects_count({base: 1}, timeslice=None)

    card = metapix.open_object(
        search_api_v2(sender.client, base).get_first().id)
    assert card.thumbnail.icons_schema in (expected_icons_card_cluster[base],
                                           expected_icons_card_no_cluster[base])


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Check object card meta {object_type}")
@pytest.mark.parametrize('object_type', ["face-male", "vehicle-type-truck", "person"])
def test_object_card_meta(metapix, object_type, sender):
    base, _, attribute = parse_object_type(object_type)
    attribute = attribute or ""  # prevent error: 'NoneType' object has no attribute 'upper'
    sender.check_min_objects_count({object_type: 1}, timeslice=None)

    card = metapix.open_object(
        search_api_v2(sender.client, object_type).get_first().id
    )
    check_card_meta(card.thumbnail.meta_text, expected_meta_card(attribute, card.id), base)
    # TODO: check object with object name (https://metapix-workspace.slack.com/archives/C03KBMWC146/p1693902804603219)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("It should be possible to display/change Object’s name and notes")
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.usefixtures('teardown_delete_object_notes')
def test_object_card_name_and_notes_persist_after_refresh(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    object_card = metapix.open_object(search_api_v2(sender.client, 'face').get_first().id)
    object_card.set_name("Test_object_face")
    object_card.set_notes("Custom note")
    object_card.save_changes()
    object_card.refresh()
    assert object_card.name == "Test_object_face"
    assert object_card.notes == "Custom note"


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Testing object back button return to search results")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1353')
def test_object_card_back_button(metapix, sender):
    # TODO: add check for bug
    # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/532
    # you should open link in a new tab or in another window
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    object_card = metapix.search("face"). \
        open_first()

    object_id = object_card.id
    search_results_page = object_card.back()
    assert search_results_page.parsed_url.path == SearchResultPageV2.path
    assert object_id in [t.id for t in search_results_page.thumbs]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Navigate to object page from search results")
def test_navigate_to_object_page(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)

    thumbnail = metapix.search('face').thumbs[0]
    thumbnail_id = thumbnail.id
    popup_dialog = thumbnail.open_popup()
    card = popup_dialog.open_card()
    assert card.thumbnail.image_url
    assert card.id == thumbnail_id


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.tag("bug")
@allure.title('All similar objects have eye icon')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/240')
@pytest.mark.clusterization_faces
def test_object_card_eyes_in_similar_objects(metapix, sender):
    '''
    FYI: https://metapix-workspace.slack.com/archives/C03KJ7TM411/p1685112922250979
    '''
    cluster = make_cluster_api(sender, 'face-female', min_cluster_size=5, timeslice=None)
    card = metapix.open_object(cluster.id, scroll_down=True)
    white_eyes = 0
    yellow_eyes = 0
    for thumb in card.similar_objects:
        if thumb.is_head_of_cluster():
            yellow_eyes += 1
        else:
            white_eyes += 1
        assert thumb.eye_cluster_size == cluster.cluster_size
    with allure.step('Check eyes amount'):
        assert yellow_eyes == 1
        assert white_eyes == cluster.cluster_size - 1


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("There is no arrow in 'cluster name' field if there is no saved cluster names")
@pytest.mark.parametrize('base', ['face'])
def test_cluster_name_no_arrow(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    obj = find_clusters_api(sender.client, base, count=1).get_first()
    object_card = metapix.open_object(obj.id)

    # TODO: find out the reason of this issue:
    # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1038
    # assert is_element_exist(lambda: object_card.input_name.button_expand) is False

    assert is_element_exist(lambda: object_card.input_name.button_collapse) is False


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Cluster name autocomple works: names are suggested only for current base")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1060")
@pytest.mark.usefixtures("teardown_delete_cluster_names")
def test_cluster_name_autocomplete(metapix, sender):
    sender.check_min_objects_count(
        {
            'face-male': 1,
            'face-female': 1,
            'vehicle-type-sedan': 1,
            'person': 1,
        },
        timeslice=None,
    )
    for object_type in ('vehicle-type-sedan', 'person', 'face-female', 'face-male'):
        obj = search_api_v2(sender.client, object_type).get_first()
        change_cluster_name(sender.client, obj, f"Test {parse_object_type(object_type)[2]}")
    object_card = metapix.open_object(obj.id)  # the last object in the loop is face-male

    # (if there is a name cluster in the database) when user opens object page
    # an arrow appears in the cluster-name field, which opens the autocomplete
    assert is_element_exist(lambda: object_card.input_name.button_expand) is True

    # when clicking to the arrow - dropdown shows available cluster_names for this base
    object_card.input_name.expand()
    assert object_card.input_name.options == {"Test male"}

    # when typing 2 symbols - result should be filtered and you can choose one of option
    object_card.set_name("Te", collapse=False)
    assert object_card.input_name.options == {"Test male", "Test female"}


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/589")
@allure.title("Check that notes in object page didn't apply for other objects in a cluster")
@pytest.mark.usefixtures('teardown_delete_object_notes')
@pytest.mark.parametrize('base', [
    pytest.param('face-male', marks=pytest.mark.clusterization_faces),
])
def test_notes_did_not_apply_to_other_objects_in_cluster(metapix, sender, base):
    cluster = metapix.open_object(
        make_cluster_api(sender, base, timeslice=None).id
    )

    cluster.set_notes("Custom note").save_changes()
    object_id_with_notes = cluster.id
    for card in cluster.similar_objects[:5]:
        another_object_page = card.open_card()
        if another_object_page.id == object_id_with_notes:
            assert another_object_page.notes == "Custom note"
        else:
            assert another_object_page.notes == ""


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Clustering. Check similar object for {object_type}")
@pytest.mark.parametrize('object_type', ['face-female'])
@pytest.mark.clusterization_faces
@pytest.mark.skip('fix it for face (different face types intersect with each other)')
def test_similar_objects_in_object_card(metapix, object_type, sender):
    object_card = metapix.open_object(
        make_cluster_api(sender, object_type, check_is_uniq=True, timeslice=None).id
    )
    # TODO: consider similar objects pagination
    assert len(object_card.similar_objects) == sender.objects_count(object_type, timeslice=None)
    assert object_card.similar_objects_count == sender.objects_count(object_type, timeslice=None)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Images in similar objects grid are different")
@pytest.mark.clusterization_faces
def test_images_different_in_similar_objects(metapix, sender):
    obj = make_cluster_api(sender, 'face-female', min_cluster_size=5, timeslice=None)
    object_card = metapix.open_object(obj.id)

    for left_card, right_card in itertools.pairwise(object_card.similar_objects):
        assert left_card.id != right_card.id
        assert left_card.image_url != right_card.image_url


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("Eye icon shown in card of clusterized object")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/240')
@pytest.mark.clusterization_faces
def test_eye_icon_shown_in_clusterized_object_card(metapix, sender):
    cluster = make_cluster_api(sender, 'face-female', timeslice=None)
    card = metapix.open_object(cluster.id)
    # TODO: split search and object_card login into separate tests
    # search = metapix.search('face')
    # assert search.objects_count > 1
    # for thumbnail in search.thumbs:
    #     assert "EYE" in thumbnail.icons_schema
    #     assert thumbnail.eye_cluster_size == cluster.cluster_size

    assert "EYE" in card.thumbnail.icons_schema
    assert card.similar_objects_count == cluster.cluster_size
    assert card.thumbnail.eye_cluster_size == cluster.cluster_size

    for similar_obj_thumb in card.similar_objects:
        assert "EYE" in similar_obj_thumb.icons_schema
        assert similar_obj_thumb.eye_cluster_size == cluster.cluster_size


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Eye icon not shown in card of object with cluster size 1")
def test_object_card_eye_not_shown_for_single_object(metapix, sender):
    sender.check_min_objects_count(
        {
            'face-with-glasses': 1,
            'face-with-beard': 1,
            # 'face-with-mask': 1,
        },
        timeslice=None,
    )
    card = metapix.open_object(
        get_objects_without_cluster(sender.client, 'face').get_first().id
    )
    assert "EYE" not in card.thumbnail.icons_schema


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.tag("bug")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/813')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/213')
@allure.title('Appearance page pagination: wrong pgoffset during pagination')
@pytest.mark.parametrize('template', [
    pytest.param('face-female', marks=pytest.mark.clusterization_faces),
])
def test_object_page_wrong_pgoffset(metapix, sender, template):
    cluster = metapix.open_object(
        make_cluster_api(sender, template, min_cluster_size=35, timeslice=None).id,
        scroll_down=False,
    )

    assert cluster.similar_objects_count > 32
    assert len(cluster.similar_objects) == 32
    cluster.similar_objects_grid.scroll_down()
    ids = [item.id for item in cluster.similar_objects]
    assert len(set(ids)) == len(ids)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1031')
@allure.title('Bad quality objects have label with information at upper-left corner')
@pytest.mark.parametrize('base', ['face'])
def test_object_thumbnail_bad_quality_label(metapix, sender, base):
    sender.check_min_objects_count({f'{base}-bad-quality': 1}, timeslice=None)
    card = metapix.open_object(
        search_api_v2(sender.client, base, consts.API_BAD_QUALITY).get_first().id
    )
    assert get_hover_tooltip(metapix, card.thumbnail.label_bad_quality). \
        startswith('Objects categorized as "bad"')


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.tag("bug")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/948')
@allure.title('Object notes is not being changed during changing cluster name')
@pytest.mark.parametrize('base', ['vehicle'])
@pytest.mark.parametrize('notes', ["Some notes. I hope it won't disappear after a while"], ids=['notes'])
def test_object_notes_remain_unchanged_during_changing_cluster_name(metapix, sender, base, notes):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    card = metapix.open_object(search_api_v2(sender.client, base).get_first().id)
    card.set_name('Test'). \
        set_notes(notes)

    card.set_name(' name', clear_with_keyboard=False)
    time.sleep(3)
    assert card.notes == notes

    card.set_name(' for cluster', clear_with_keyboard=False)
    time.sleep(3)
    assert card.notes == notes


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1071')
@allure.title('Object popup: check zoom works')
@pytest.mark.parametrize('base', ['vehicle'])
def test_thumbnail_popup_zoom(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    card = metapix.open_object(search_api_v2(sender.client, base).get_first().id)
    popup_dialog = card.thumbnail.open_popup()
    initial_image_state = popup_dialog.img_container.screenshot_as_png

    popup_dialog.zoom_in()
    check_images_are_not_equal(popup_dialog.img_container.screenshot_as_png, initial_image_state)

    popup_dialog.reset_scale()
    check_images_are_equal(popup_dialog.img_container.screenshot_as_png, initial_image_state)


def generate_title(base, obj):
    meta = obj.meta
    if base == 'face':
        return f'{base.capitalize()} - {meta["gender"].capitalize()}, {meta["age"]}'
    raise RuntimeError(f'Base is not supported: {base}')


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Check card popup header title for {base}")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1178')
@pytest.mark.parametrize('base', ['face'])
def test_card_popup_headler_title(metapix, base, sender):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    obj = search_api_v2(sender.client, base)[0]
    popup_dialog = metapix.open_object(obj.id). \
        thumbnail.open_popup()
    assert generate_title(base, obj) == popup_dialog.title


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Check eye icon tooltips are correct")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1206')
@pytest.mark.parametrize('object_type', [
    pytest.param('face-male', marks=pytest.mark.clusterization_faces),
])
def test_card_eye_icon_tooltips(metapix, object_type, sender):
    cluster = make_cluster_api(sender, object_type, min_cluster_size=5, timeslice=None)
    card = metapix.open_object(cluster.id, scroll_down=False)

    assert card.thumbnail.is_head_of_cluster()  # self-check: make sure we have just opened a main object
    assert get_hover_tooltip(metapix, card.similar_objects[0]._eye) == 'GROUPED OBJECTS'
    assert get_hover_tooltip(metapix, card.thumbnail._eye) == 'MAIN GROUPED OBJECT'


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Object page url has company id")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1192')
def test_card_url_has_company_id(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    card = metapix.search('face', fetch_more=False). \
        thumbs.get_first(). \
        open_card()
    company_id = get_active_company(sender.client).id
    assert re.findall(fr'.*?/appearances/{company_id}/\d+', card.url)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("cluster name has validation")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1224')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1356')
def test_cluster_name_validation(metapix, sender):
    '''
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/343
    allow "a-zA-Z0-9 _"
    max length: 100
    '''
    check_cluster_name = partial(
        check_input_validation,
        valid=['tester', 'test2324', 'Joshn Smith', 'Under_score', 'Hello'*19],
        invalid=['=', 'Ga/-124', '*', 'Я русский', 'Hello'*21],
    )
    sender.check_min_objects_count({'face': 1}, timeslice=None)

    with allure.step('Check object card'):
        card = metapix.open_object(search_api_v2(sender.client, 'face').get_first().id)
        check_cluster_name(control=card.input_name, button=card.button_save_changes)


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Object page")
@allure.title("Persons does not support clusterization")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1269')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1319')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1492')
@pytest.mark.parametrize('base', ['person'])
def test_clusterization_is_not_supported(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    obj = search_api_v2(sender.client, base).get_first()
    with LastRequestsContext(metapix.driver) as get_last_req_func:
        card = metapix.open_object(obj.id)
        requests = get_last_req_func(url='v2/search/person')
    assert not requests, 'There are search requests were sent during opening person object card'
    assert card.message == 'Currently, this object type is not clusterized'


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('It is possible to zoom similar objects in object page')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1308')
@pytest.mark.parametrize('base', ['face'])
def test_object_page_zoom(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    card = metapix.open_object(search_api_v2(sender.client, base).get_first().id)
    check_zoom(card.similar_objects_grid, check_state_persistence=False)


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.tag('bug')
@allure.title('It is possible to search cluster name in object page')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1234')
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_object_page_search_by_cluster_name(metapix, sender):
    sender.check_min_objects_count({'face-male': 1, 'face-female': 1}, timeslice=None)

    objects = get_suitable_objects(sender, ['face'], allow_single_objects=True, count=3, min_cluster_size=1)
    for ix, obj in enumerate(objects):
        change_cluster_name(sender.client, obj, f'cluster {ix}')
    card = metapix.open_object(search_api_v2(sender.client, 'face').get_first().id)

    test_data = (
        ('hello', set()),
        ('cluster', {'cluster 0', 'cluster 1', 'cluster 2'}),
        ('cluster 1', {'cluster 1'}),
    )

    def check_case(cluster_name, expected_result):
        with allure.step(f'Check cluster names for "{cluster_name}"'):
            card.input_name.type_text(cluster_name, clear_with_keyboard=True)
            try:
                card.input_name.expand()
                # ATTENTION! Why do I type text, collapse "Cluster's name" input and
                # expand the input agait? I could just type text and immediatelly check options..
                # but "cluster name" options have different XPATHs depends on
                # when the options is being shown: right after typing text or after expanding
                # TODO: consider antoher XPATH for dropdown in "Cluster's name" input
            except DropdownExpandException:
                assert expected_result == set()
            else:
                assert card.input_name.options == expected_result

    for cluster_name, expected_result in test_data:
        check_case(cluster_name, expected_result)


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('Opened object from cluster has a border')
@pytest.mark.clusterization_faces
def test_object_page_opened_object_has_border(metapix, sender):
    cluster = make_cluster_api(sender, 'face-female', min_cluster_size=5, timeslice=None)
    card = metapix.open_object(cluster.id, scroll_down=True)
    highlighted_ids = [t.id for t in card.similar_objects if t.has_highlighted_border() is True]
    assert len(highlighted_ids) == 1
    assert highlighted_ids[0] == cluster.id


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.tag('bug')
@allure.title('The "Add subscription" toggle should not be displayed')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1388')
def test_object_card_no_add_sub_toggle(metapix, sender):
    sender.check_min_objects_count({'face': 1}, timeslice=None)
    card = metapix.open_object(search_api_v2(sender.client, 'face').get_first().id)
    assert is_element_exist(lambda: card.sub_toggle) is False


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('Vehicle object without license plate does not have any similar objects')
def test_vehicle_no_license_plate(metapix, sender):
    obj = next(get_objects_without_license_plate(sender))
    card = metapix.open_object(obj.id)
    assert card.thumbnail.license_plate == 'N/A'
    assert card.message == 'No similar objects found'


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('Check vehicle object with uniq license plate')
def test_vehicle_uniq_license_plate(metapix, sender):
    sender.check_min_objects_count(
        {'vehicle': 1},
        meta={consts.META_LIC_PLATE: 'uniq_lic_plate'},
        timeslice=None,
    )
    obj = get_object_with_uniq_license_plate(sender)
    card = metapix.open_object(obj.id)
    assert card.thumbnail.license_plate.lower() == obj.meta['license_plate'].lower()
    assert len(card.similar_objects) == 1
    assert card.similar_objects[0].id == obj.id
    assert card.similar_objects[0].has_highlighted_border()


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@allure.title('Check vehicle object with non-uniq license plate')
def test_vehicle_non_uniq_license_plate(metapix, sender):
    sender.check_min_objects_count({'vehicle': 3}, meta=consts.META_LIC_PLATE_12345)
    objects = tuple(get_objects_with_non_equal_license_plate(sender, min_amount=3))
    obj = objects[0]
    card = metapix.open_object(obj.id)
    assert card.thumbnail.license_plate.lower() == obj.meta['license_plate'].lower()
    assert card.similar_objects_count is None   # FYI concerning "Similar objects" count: https://metapix-workspace.slack.com/archives/C03KBMWC146/p1719961192633369
    assert len(card.similar_objects) == len(objects)
    assert set(card.similar_objects_grid.ids) == set(obj.id for obj in objects)


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.title('Check very long object name in thumbnail is truncated')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1484')
@pytest.mark.parametrize('cluster_name', ['VeryLongClusterName' * 5])
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.skip('Find out the way to get tooltip text with applied css styles')
def test_very_long_cluster_name_is_truncated(
        metapix: RootPage,
        cluster_name: str,
        base: BaseType,
        sender: ImageSender):
    def get_face_information(thumbnail: ObjectThumbnail) -> Sequence[str]:
        '''
        FACE INFORMATION
        FEMALE 39
        CLUSTER NAME
        LONG CLUSTER NAME
        '''
        meta_element = thumbnail.meta_elements[1]
        text = get_hover_tooltip(metapix, meta_element).split('\n')
        if len(text) != 4:
            raise RuntimeError
        return text

    obj = search_api_v2(sender.client, base).get_first()
    change_cluster_name(sender.client, obj, cluster_name)

    results = metapix.search(base, {consts.FILTER_OBJECTS_NAME: '*'})
    face_information = get_face_information(results.thumbs.get_first())
    assert face_information[0] == 'FACE INFORMATION'
    raise NotImplementedError('modify HTML to make cluster name lenght at least 300 chars. Backend allows to set 100char cluster name maximim')
    raise NotImplementedError('find out the way too long cluster name should be truncated')
    raise NotImplementedError('Check thumbnails: 1) search results 2) object card 3) live feed widget')


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@pytest.mark.parametrize('cluster_name', ['ClusterMain'])
@allure.title('Changing the cluster name changes names from all similar objects')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1451')
def test_new_cluster_name_applies_for_similar_objects(
        cluster_name: str, metapix: RootPage, sender: ImageSender):
    obj = make_cluster_api(sender, 'face-male', min_cluster_size=4, timeslice=None)
    card = metapix.open_object(obj.id)
    card.set_name(cluster_name).save_changes()

    with allure.step('Check that new cluster name applied for all similar objects'):
        assert card.similar_objects, 'There are no similar objects'
        for thumb in card.similar_objects:
            assert cluster_name == thumb.cluster_name_from_meta


@allure.epic('Frontend')
@allure.suite('Advanced Search')
@allure.story('Object page')
@pytest.mark.parametrize('object_name', ['buttonsave'])
@allure.title('Save button should not be active if changes on object card erased')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1434')
def test_save_button_not_active_if_changes_erased(object_name: str, metapix: RootPage, sender: ImageSender):
    sender.check_min_objects_count({'face': 3}, timeslice=None)
    card = metapix.open_object(search_api_v2(sender.client, 'face').get_first().id)

    with allure.step('check "save" button is not active by default'):
        assert not card.button_save_changes.is_active()

    with allure.step('Check "save" button became active if "object name" has been changed'):
        card.set_name(object_name)
        assert card.button_save_changes.is_active()

    with allure.step('Check "save" button became inactive if all changes have been reverted'):
        card.set_name("")
        assert not card.button_save_changes.is_active()


@allure.epic('Frontend')
@allure.story('Object page')
@allure.suite('Advanced Search')
@allure.title('There should be pop-up if cluster name changes which added to watchlist')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1434')
@pytest.mark.parametrize("cluster_name,new_cluster_name", [('clustername', 'changeclustername')])
@pytest.mark.usefixtures('teardown_delete_cluster_names')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_actions_with_predicates_name_if_cluster_name_changes(
        cluster_name: str,
        new_cluster_name: str,
        metapix: RootPage,
        sender: ImageSender,
        client: ApiClient,
        another_driver: CustomWebDriver,
):
    with allure.step('Preparations for test'):
        sender.check_min_objects_count({'face': 1}, timeslice=None)
        obj = search_api_v2(sender.client, consts.BASE_FACE).get_first()
        change_cluster_name(sender.client, obj, cluster_name)
        wl = create_watchlist(client, 'wl', 'face')
        add_predicates(client, wl, create_face_predicates(cluster_name=cluster_name))
        filters = auth_user_in_browser(another_driver). \
            open_watchlists().get('wl'). \
            open_filters()

    with allure.step('Change cluster name and discard changing watchlis'):
        card = metapix.open_object(obj.id)
        card.set_name(new_cluster_name)
        card.button_save_changes.click()
        assert card.change_cluster_name_popup.message == 'Changing the cluster name will update it across all relevant Watch Lists. Are you sure you want to continue?'
        card.change_cluster_name_popup.cancel()
        assert filters.refresh().schema == [{'Cluster Name': cluster_name, 'Age': 'All ages', 'Gender': 'All genders'}]

    with allure.step('Change cluster name and confirm changing watchlis'):
        card.set_name(new_cluster_name)
        card.button_save_changes.click()
        card.change_cluster_name_popup.confirm()
        assert filters.refresh().schema == [{'Cluster Name': new_cluster_name, 'Age': 'All ages', 'Gender': 'All genders'}]


@allure.epic('Frontend')
@allure.story('Object page')
@allure.suite('Advanced Search')
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1552')
@allure.title('App does not crash in case cluster name is selected for person')
@pytest.mark.usefixtures('teardown_delete_cluster_names')
def test_person_select_cluster_name(metapix: RootPage, sender: ImageSender):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({'person': 2}, timeslice=None)
        obj_with_name, obj_to_select_name = search_api_v2(sender.client, 'person')[:2]

    with allure.step('Set object name for any cluster to be able to select cluster name from dropdown'):
        change_cluster_name(sender.client, obj_with_name, 'test_name')

    with allure.step('Select cluster name from dropdown'):
        card = metapix.open_object(obj_to_select_name.id)
        card.select_name('test_name'). \
            save_changes()


@allure.epic('Frontend')
@allure.story('Object page')
@allure.suite('Advanced Search')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1608')
@allure.title('Check tooltips for meta information in object thumbnail: main thumbnail in object card')
@pytest.mark.parametrize('base', ['vehicle'])
def test_object_thumb_meta_tooltips_object_card_main_thumb(sender: ImageSender, metapix: RootPage, base: BaseType):
    with allure.step('Prepare data'):
        sender.check_min_objects_count({base: 1}, timeslice=None)
        obj = search_api_v2(sender.client, base).get_first()
        card = metapix.open_object(obj.id)

    with allure.step('Check tooltips for object main thumbnail'):
        check_thumbnail_meta_tooltips(card.thumbnail, base, obj)


@allure.epic('Frontend')
@allure.story('Object page')
@allure.suite('Advanced Search')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1608')
@allure.title('Check tooltips for meta information in object thumbnail: similar object in object card')
@pytest.mark.clusterization_faces
def test_object_thumb_meta_tooltips_object_card_similar_object(sender: ImageSender, metapix: RootPage):
    with allure.step('Prepare data'):
        cluster = make_cluster_api(sender, 'face-female', min_cluster_size=2, timeslice=None)
        card = metapix.open_object(cluster.id)

    with allure.step('Check tooltips for similar object'):
        assert card.similar_objects, 'There are no similar objects'
        similar_object_thumb = card.similar_objects[0]
        check_thumbnail_meta_tooltips(
            similar_object_thumb,
            'face',
            get_object(sender.client, similar_object_thumb.id),
        )
