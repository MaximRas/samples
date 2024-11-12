import allure
import pytest

import consts
from tools import run_test
from tools import send_value_to_test
from tools.steps import create_any_chart
from tools.types import ApiUserRole
from tools.users import auth_user_in_browser
from tools.users import get_or_create_second_company
from tools.users import get_second_user_client

from pages.base_page import NoElementException
from pages.base_page import is_element_exist
from pages.layout.layout_listbox import LayoutPage

from tests_webui.regression.widgets import check_autorefresh_works
from tests_webui.regression.widgets import check_change_timeslice
from tests_webui.regression.widgets import check_filtering_works
from tests_webui.regression.widgets import check_is_not_possible_to_create_widget
from tests_webui.regression.widgets import check_is_possible_to_rename_widget
from tests_webui.regression.widgets import check_delete_widget
from tests_webui.regression.widgets import check_shared_widget_keeps_camera_state
from tests_webui.regression.widgets import check_shared_widget_keeps_location_state

pytestmark = [
    pytest.mark.regression,
]


@pytest.fixture(scope='function', autouse=True)
def teardown_delete_layouts(teardown_delete_layouts):
    ''' Make this fixture autousable for this suite '''


@pytest.fixture(scope="module")
def client_admin(client):
    """ Another user from same company as `client` """
    second_user_client = get_second_user_client(
        client=client,
        role=ApiUserRole.admin,
        first_name='Admin',
        last_name='User',
    )
    assert client.user.email != second_user_client.user.email  # self check
    assert client.company.name == second_user_client.company.name  # self check
    return second_user_client


@pytest.fixture(scope="module")
def add_second_company_to_admin(client_admin):
    return get_or_create_second_company(client_admin, role=ApiUserRole.admin)


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.tag("bug")
@allure.title("Sharing layout should not create new layout")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/608")
def test_share_layout_doest_create_new_layout(metapix):
    metapix.layout.share(another_driver=None)

    assert metapix.layout.available_layouts == \
        [LayoutPage.DEFAULT_LAYOUT_NAME]


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to add more than 6 number of widgets")
def test_add_more_than_6_widgets(metapix):
    widgets_count = 0
    while True:
        try:
            metapix.dashboard.open_widget_builder(). \
                create_value_widget(
                    object_type="person", title=f"Widget #{widgets_count}")
        except NoElementException:
            break
        widgets_count += 1
        if widgets_count > 6:
            break
    else:
        pytest.fail(f"It is possible to add only {widgets_count} widgets")


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to copy layout with widgets")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/609")
def test_copy_layout_with_widgets(metapix, sender):
    sender.check_diff_objects_count(["face", "person"])
    widget_face = metapix.dashboard.open_widget_builder().\
        create_value_widget(object_type="face")
    widget_person = metapix.dashboard.open_widget_builder().\
        create_value_widget(object_type="person")

    copied_layout = metapix.layout.copy("Copied layout")

    assert metapix.dashboard.widgets_titles == copied_layout.widgets_titles
    widget_face.assert_objects_count(sender.objects_count('face'))
    widget_person.assert_objects_count(sender.objects_count('person'))


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to delete layout")
@pytest.mark.parametrize('base', ['vehicle'])
def test_delete_layout_with_widgets(metapix, base):
    metapix.layout.add("Another layout")

    metapix.dashboard.open_widget_builder().\
        create_value_widget(object_type=base)

    metapix.layout.delete()
    assert metapix.layout.available_layouts == [LayoutPage.DEFAULT_LAYOUT_NAME]


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("It should be possible to rename layout")
def test_rename_layout(metapix):
    metapix.layout.add("Another layout")   # do not touch 'Default' layout
    metapix.layout.rename("Renamed layout")
    assert metapix.layout.current_layout == "Renamed layout"
    assert metapix.layout.available_layouts == \
        [LayoutPage.DEFAULT_LAYOUT_NAME, "Renamed layout"]


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/486")
@allure.title("Layout cannot be named or renamed with an empty name")
def test_not_possible_to_assign_empty_name_to_layout(metapix):
    modify_dialog = metapix.layout.open_add_dialog().set_value("")
    assert modify_dialog.input_value.tooltip
    modify_dialog.cancel()

    modify_dialog = metapix.layout.open_rename_dialog().set_value("")
    assert modify_dialog.input_value.tooltip
    modify_dialog.cancel()


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/522")
@allure.title("Default layout name shown after deleting another layout")
def test_default_layout_name_shown_after_deletion(metapix):
    new_layout_name = "Another layout"
    metapix.layout.add(new_layout_name)
    assert metapix.layout.current_layout == new_layout_name
    metapix.layout.delete()
    assert metapix.layout.current_layout == LayoutPage.DEFAULT_LAYOUT_NAME


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Check cancelling deleting a layout: the layout remains undeleted")
def test_cancel_delete_layout(metapix):
    new_layout_name = "Another layout"
    metapix.layout.add(new_layout_name)

    metapix.layout.open_delete_dialog().cancel()
    assert metapix.layout.current_layout == new_layout_name


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Owner (has 1 company) shares layout to himself")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/616")
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'test_function', [
        check_is_not_possible_to_create_widget,
        check_filtering_works,
        check_change_timeslice,
        check_autorefresh_works,
        check_is_possible_to_rename_widget,
        check_delete_widget,
    ],
    ids=['create_widget', 'filtering', 'timeslice', 'autorefresh', 'rename_widget', 'delete_widget'],
)
def test_shared_layout_owner_with_1_company_himself(metapix, another_driver, sender, base, test_function):
    """
    User #1                           User #1
       |           >>> share >>>         |
    Company #1                        Company #1
    """
    auth_user_in_browser(another_driver)
    widget = create_any_chart(metapix.dashboard, base)

    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=widget)

    test_function(
        sender=sender,
        layout=shared_layout,
        widget=shared_widget,
        base=base,
    )


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Owner shares layout to ANOTHER user in the same company (both have 1 companies)")
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'test_function', [
        check_is_not_possible_to_create_widget,
        check_filtering_works,
        check_change_timeslice,
        check_autorefresh_works,
        check_is_possible_to_rename_widget,
        check_delete_widget,
    ],
    ids=['create_widget', 'filtering', 'timeslice', 'autorefresh', 'rename_widget', 'delete_widget'],
)
def test_shared_layout_user_from_same_company_both_have_1_company(
        metapix, another_driver, client_admin, sender, base, test_function):
    """
    User #1                           User #2
       |           >>> share >>>         |
    Company #1                        Company #1
    """
    auth_user_in_browser(another_driver, client_admin)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)

    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=widget)

    test_function(
        sender=sender,
        layout=shared_layout,
        widget=shared_widget,
        base=base,
    )


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Opening a shared layout by a user from another company is not available")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/636")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/733")
@pytest.mark.parametrize('base', ['face'])
def test_shared_layout_user_from_other_company(
        metapix, another_driver, client_spc, sender, base):
    """
    User #1                           autotest@metapix.ai
       |           >>> share >>>              |
    Company #1                        Metapix Test
    """
    auth_user_in_browser(another_driver, client_spc)
    metapix.dashboard.open_widget_builder().\
        create_bar_chart_widget(object_type=base)

    assert is_element_exist(lambda: metapix.layout.share(another_driver)) is False


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Owner (has 2 companies) shares the layout for himself")
@pytest.mark.usefixtures('second_company')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'test_function', [
        check_is_not_possible_to_create_widget,
        check_filtering_works,
        check_change_timeslice,
        check_autorefresh_works,
        check_is_possible_to_rename_widget,
        check_delete_widget,
    ],
    ids=['create_widget', 'filtering', 'timeslice', 'autorefresh', 'rename_widget', 'delete_widget'],
)
def test_shared_layout_owner_with_2_companies_himself(
        metapix, sender, another_driver, base, test_function):
    """
    User #1                           User #1
       |           >>> share >>>         |
    Company #1                        Company #1
    Company #2                        Company #2
    """
    auth_user_in_browser(another_driver)
    widget = metapix.dashboard.open_widget_builder().\
        create_bar_chart_widget(object_type=base)

    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=widget)

    test_function(
        sender=sender,
        layout=shared_layout,
        widget=shared_widget,
        base=base,
    )


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title("Owner shares the layout to ANOTHER user in the same company (both have 2 companies)")
@pytest.mark.usefixtures('second_company')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.parametrize(
    'test_function', [
        check_is_not_possible_to_create_widget,
        check_filtering_works,
        check_change_timeslice,
        check_autorefresh_works,
        check_is_possible_to_rename_widget,
        check_delete_widget,
    ],
    ids=['create_widget', 'filtering', 'timeslice', 'autorefresh', 'rename_widget', 'delete_widget'],
)
def test_shared_layout_user_from_same_company_both_have_2_companies(
        metapix, sender, another_driver, client_admin, add_second_company_to_admin, base, test_function):
    """
    User #1                           User #2
       |           >>> share >>>         |
    Company #1                        Company #1
    Company #2                        Company #3
    """
    # TODO: check both users have two companies (1 common company)
    auth_user_in_browser(another_driver, client_admin)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type=base)
    shared_layout = metapix.layout.share(another_driver)
    shared_widget = shared_layout.get_widget(origin=widget)

    test_function(
        sender=sender,
        layout=shared_layout,
        widget=shared_widget,
        base=base,
    )


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/400")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/618")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/631")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/660")
@allure.title("Shared layout is affected when changing")
def test_widget_changes_on_shared_layout(metapix, sender, another_driver):
    auth_user_in_browser(another_driver)
    sender.check_diff_objects_count(consts.FACE_GENDERS)
    widget = metapix.dashboard.open_widget_builder().\
        create_bar_chart_widget(object_type='face')

    shared_layout = metapix.layout.share(another_driver)

    # Change widget on new layout
    shared_widget = shared_layout.get_widget(origin=widget)
    shared_widget.open_settings().select_gender("male").apply()
    shared_widget.assert_objects_count(sender.objects_count('face', consts.META_MALE))

    metapix.refresh()
    widget.assert_objects_count(sender.objects_count('face'))
    assert metapix.layout.current_layout == LayoutPage.DEFAULT_LAYOUT_NAME


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/398")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/609")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/622")
@allure.title("Changing widget on copied layout does not affect the original widget ")
def test_widget_changes_on_copied_layout(metapix, sender):
    sender.check_diff_objects_count(consts.FACE_GENDERS)
    widget = metapix.dashboard.open_widget_builder(). \
        create_bar_chart_widget(object_type='face')

    metapix.layout.copy("Another layout")
    copied_widget = metapix.dashboard.get_widget(origin=widget)
    copied_widget.open_settings(). \
        select_gender("male").apply()
    copied_widget.assert_objects_count(sender.objects_count('face', consts.META_MALE))

    metapix.switch_to_default_layout()
    widget.assert_objects_count(sender.objects_count('face'))


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title('Check that widget on shared layout keeps camera state of original widget')
@pytest.mark.parametrize('base', ['face'])
def test_shared_layout_widget_keeps_camera_state(metapix, another_driver, sender, base):
    auth_user_in_browser(another_driver)
    widget = create_any_chart(metapix.dashboard, base)
    test = run_test(check_shared_widget_keeps_camera_state(widget, base, sender, check_settings=True))
    shared_layout = metapix.layout.share(another_driver)
    send_value_to_test(test, shared_layout.get_widget(origin=widget))


@allure.epic("Frontend")
@allure.suite("Layouts")
@allure.title('Check that widget on shared layout keeps locatoin state of original widget')
@pytest.mark.parametrize('base', ['face'])
@pytest.mark.usefixtures('teardown_delete_locations')
def test_shared_layout_widget_keeps_loc_state(metapix, another_driver, sender, base):
    auth_user_in_browser(another_driver)
    widget = create_any_chart(metapix.dashboard, base)
    test = run_test(check_shared_widget_keeps_location_state(widget, base, sender, check_settings=True))
    shared_layout = metapix.layout.share(another_driver)
    send_value_to_test(test, shared_layout.get_widget(origin=widget))
