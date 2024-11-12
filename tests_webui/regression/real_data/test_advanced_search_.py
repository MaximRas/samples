import time

import allure
import pytest

import consts
from tools.users import auth_user_in_browser
from tools import get_xhr_requests
from tools.time_tools import Ago
from pages.base_page import is_element_exist
from pages.object_card import ObjectCard

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/507")
@allure.title("New search results must be loaded while scrolling to bottom of the results page")
def test_objects_loaded_when_scrolling_to_bottom(metapix):
    search = metapix.search('face', fetch_more=False)
    initial_num_objs = search.objects_count
    search.scroll_down(times=1)
    assert search.objects_count > initial_num_objs


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/516")
@allure.title("Search results not loaded when results page is not being scrolled down")
def test_search_results_not_loaded_when_not_scrolled(metapix):
    def collect_search_requests():
        return [r["name"] for r in get_xhr_requests(metapix._driver) if "object-manager/search/" in r["name"]]

    metapix.search('face')
    search_requests = collect_search_requests()
    time.sleep(40)
    assert collect_search_requests() == search_requests


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/141")
@allure.title("Objects not accessible by users from other companies")
def test_objects_not_accessible_from_other_companies(metapix, another_driver, verified_client):
    auth_user_in_browser(another_driver, verified_client)
    object_card = metapix.search(consts.BASE_FACE, fetch_more=False). \
        open_first()
    obj_url = object_card.url
    object_card_other_company = ObjectCard(
        driver=another_driver,
        open_page=False,
        check_primary_element=False
    ).open(obj_url)

    object_card_other_company.assert_tooltip(f"Error: Object '{object_card.id}' does not exist")
    assert is_element_exist(lambda: object_card_other_company.name) is False


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("Searching with filter face:gender=Female doesn't return other gender")
@pytest.mark.smoke
def test_search_face_dropdown_filters(metapix):
    search = metapix.search(consts.BASE_FACE, consts.FILTER_FEMALE, fetch_more=False)

    for card in range(10):
        assert 'FEMALE' in [s.replace(',', '') for s in search.thumbs[card].meta_text[1].split()]


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title("Timeout when search by dates")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/object-management/object-manager/-/issues/233")
def test_advanced_search_timeout_when_search_by_dates(metapix):
    results = metapix.search('vehicle', consts.FILTER_ORDER_BY_OLD_TO_NEW, fetch_more=False)
    metapix.assert_no_error_tooltips()
    assert results.objects_count > 0

    results = metapix.search('face', {consts.FILTER_START_PERIOD: Ago('-10h').dt}, fetch_more=False)
    metapix.assert_no_error_tooltips()
    assert results.objects_count > 0
