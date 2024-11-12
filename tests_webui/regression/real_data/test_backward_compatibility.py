import math
import hashlib
from contextlib import suppress

import allure
import pytest

import consts
from pages.widgets import BarChartNotShared
from pages.widgets import SwitchBarLineChartExeption

from tests_webui.regression.real_data import switch_2w_timeslice
from tests_webui.regression.real_data import set_custom_timeslice

pytestmark = [
    pytest.mark.regression,
]


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Old user: licenses remain unchanged")
def test_license_installed(metapix):
    licenses = metapix.open_settings(). \
        open_licenses()
    assert len(licenses.schema) > 0


@allure.epic("Frontend")
@allure.suite("Profile")
@allure.title("Old user: avatar shouldn't be change or disappear")
def _test_avatar_exists(metapix):
    # TODO: fix this test
    general_settings = metapix.open_settings(). \
        open_general()
    assert hashlib.sha1(general_settings.user_image.screenshot_as_png).hexdigest() == \
        "aadf4025a1b15ed2aec2dd4a08ee5f7a43fa0ab1"


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("Old user should be able to find clusters by name")
def test_object_name_exists(metapix):
    # TODO: check there is only one cluster was found. And there is cluster name if I open object from cluster
    search_results = metapix.search("face", {consts.FILTER_OBJECTS_NAME: "tongue_man"}, fetch_more=False)
    assert search_results.objects_count > 1


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.story("Clusterization")
@allure.title("Old user should be able to find object by note")
def test_object_note_exists(metapix):
    """ object's note: Elderly Man shows tongue """
    search_results = metapix.search("face", {consts.FILTER_OBJECTS_NOTES: "Elderly Man"}, fetch_more=False)
    assert search_results.objects_count == 1


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Old user should be able to create/modify/delete a new widget")
def test_is_able_to_create_modify_delete_widget(metapix):
    widget = metapix.dashboard. \
        open_widget_builder(). \
        create_bar_chart_widget(object_type="vehicle")
    set_custom_timeslice(widget)

    try:
        vehicle_objects_amount = widget.objects_count
        widget.open_settings().select_base("face").apply()
        metapix.waiter(timeout=10).until(
            lambda x: not math.isclose(widget.objects_count, vehicle_objects_amount, abs_tol=100)
        )

        face_objects_amount = widget.objects_count
        widget.open_settings().select_gender("female").apply()
        metapix.waiter(timeout=10).until(
            lambda x: not math.isclose(widget.objects_count, face_objects_amount, abs_tol=100)
        )

    finally:
        widget.delete()


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Old user: it is possible to create/modify/delete layout")
def test_layout_create_modify_delete(metapix):
    # TODO: add teardown (delete another layout)
    metapix.layout.add("Another layout")
    metapix.open_dashboard(). \
        open_widget_builder().\
        create_bar_chart_widget(object_type="person")
    metapix.layout.delete()
    assert "Another layout" not in metapix.layout.available_layouts


@allure.epic("Frontend")
@allure.suite("Widgets")
@allure.title("Old user should be able to change old widget")
def test_change_old_widget(metapix, driver):
    widget = BarChartNotShared(title="Bar / Line Chart", driver=driver)
    with suppress(SwitchBarLineChartExeption):
        widget.switch_to_bar_chart()
    switch_2w_timeslice(widget.wait_spinner_disappeared())
    available_bases = ["Face", "Vehicle"]
    current_amount = widget.objects_count
    settings = widget.open_settings()

    # Choose another base
    available_bases.remove(settings.filter_base.value)
    settings.select_base(available_bases[0]).apply()
    metapix.waiter(timeout=10).until(
        lambda x: not math.isclose(widget.objects_count, current_amount, abs_tol=100)
    )
