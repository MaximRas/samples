"""
NOTE: Remember that camera order is UNDEFINED!!!
▲ stands for "expanded"
▼ stands for "collapsed"
"""
import time

from contextlib import suppress
from pages.device_tree.device_tree_page import DeviceTreePage
from typing import Iterable
from typing import Callable
import logging

import allure
import pytest

import consts
from tools import UndefinedElementException
from tools.cameras import CameraData
from tools.cameras import archive_camera
from tools.cameras import change_analytics
from tools.cameras import create_camera
from tools.cameras import delete_all_cameras_for_client
from tools.cameras import disable_camera
from tools.cameras import enable_camera
from tools.cameras import get_camera_by_name
from tools.cameras import get_cameras
from tools.cameras import rename_camera
from tools.cameras import unarchive_camera
from tools.client import ApiClient
from tools.image_sender import UnprocessableEntityException
from tools.locations import bind_camera_to_location_by_id
from tools.locations import bind_camera_to_location_by_name
from tools.steps import check_input_validation
from tools.steps import create_location_schema_api
from tools.steps import create_widget_api

from pages.base_page import ElementStillExistsException
from pages.input_base import has_clear_button
from pages.base_page import is_element_exist
from pages.device_tree import NO_CAMERAS
from pages.device_tree import NO_RESULTS
from pages.device_tree.add_edit_loc_dialog import AddLocDialog
from pages.input_field import Input_v0_48_4
from pages.root import RootPage

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)


def archive_cameras_by_name(client: ApiClient, *args: Iterable[str]):
    ''' archive several cameras with api '''
    with allure.step(f'Archive cameras: {args}'):
        log.info(f'Archive cameras {args} for {client}')
        cameras = get_cameras(client)
        for camera_name in args:
            camera = next(filter(lambda x: x.name == camera_name, cameras))
            archive_camera(client, camera)


def camera_info_displayed(device_tree: DeviceTreePage, bounded_camera=None) -> bool:
    time.sleep(2)
    if bounded_camera is not None:
        camera = device_tree.get_bound_camera(bounded_camera)
        return bool(camera.tags)
    else:
        for camera in device_tree._get_all_cameras():
            if camera.tags:
                return True
        return False

@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It should be possible to archive/unarchive cameras")
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_archive_unarchive_cameras(metapix, client):
    create_location_schema_api(client, {
        'Building 1': [
            'camera-1',
            {'Cellar': ['camera-2']}
        ]
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()

    with allure.step('Unassigned -> Archived'):
        device_tree.unassigned_cameras.get('camera-3').archive()
        assert device_tree.cameras_schema == {
            'Location Not Specified': {'camera-4'},
            'Disabled': {'camera-3'},
        }

    with allure.step('Location -> Archived'):
        device_tree.get_bound_camera('Building 1 > camera-1').archive()
        assert device_tree.cameras_schema == {
            'Location Not Specified': {'camera-4'},
            'Disabled': {'camera-1', 'camera-3'},
        }
        assert device_tree.loc_schema == {'▲ Building 1': [{'▲ Cellar': ['camera-2']}]}

    with allure.step('Archived -> Unassingned'):
        device_tree.archived_cameras.get('camera-1').unarchive()
        device_tree.archived_cameras.get('camera-3').unarchive()
        # check there is no "Archived" section
        # check unarchived cameras moved to "Not specified" section
        assert device_tree.cameras_schema == {
            'Location Not Specified': {'camera-1', 'camera-3', 'camera-4'},
        }
        assert device_tree.loc_schema == {'▲ Building 1': [{'▲ Cellar': ['camera-2']}]}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It should be possible to create/delete locations")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_create_delete_locations_ui(metapix, client):
    '''
    This test comprise of different scenarios:
     - creating locations (manually, thr UI)
     - deleting locations (manually, thr UI)

    TODO: Shold I separate these scenarios?
    '''
    device_tree = metapix.open_device_tree()

    with allure.step('Create root loc with ico button in header'):
        device_tree.add_root_loc('Empty loc')

    with allure.step('Create nested locs with loc menu buttons'):
        device_tree.add_nested_loc('Building 1 > Nested 1 (empty)')
        device_tree.add_nested_loc('Building 1 > Nested 2 (with child loc) > Stairs')
        device_tree.add_nested_loc('Building 1 > Nested 3 (with camera)')
        device_tree.add_nested_loc('Building 1 > Nested 4 (filler)')

    bind_camera_to_location_by_name(client, 'camera-1', 'Nested 3 (with camera)')
    bind_camera_to_location_by_name(client, 'camera-2', 'Nested 4 (filler)')
    device_tree.refresh(). \
        expand_all_locations_manually()

    assert device_tree.loc_schema == {
        'Empty loc': [],
        '▲ Building 1': [
            {'Nested 1 (empty)': []},
            {'▲ Nested 2 (with child loc)': [{'Stairs': []}]},
            {'▲ Nested 3 (with camera)': ['camera-1']},
            {'▲ Nested 4 (filler)': ['camera-2']},
        ],
    }

    with allure.step('Delete empty loc'):
        device_tree.get_loc('Empty loc').delete()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'Nested 1 (empty)': []},
                {'▲ Nested 2 (with child loc)': [{'Stairs': []}]},
                {'▲ Nested 3 (with camera)': ['camera-1']},
                {'▲ Nested 4 (filler)': ['camera-2']},
            ],
        }

    with allure.step('Delete child loc'):
        device_tree.get_loc('Building 1 > Nested 1 (empty)').delete()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Nested 2 (with child loc)': [{'Stairs': []}]},
                {'▲ Nested 3 (with camera)': ['camera-1']},
                {'▲ Nested 4 (filler)': ['camera-2']},
            ],
        }

    with allure.step('Delete loc contains child loc'):
        device_tree.get_loc('Building 1 > Nested 2 (with child loc)').delete()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Nested 3 (with camera)': ['camera-1']},
                {'▲ Nested 4 (filler)': ['camera-2']},
            ],
        }

    with allure.step('Delete loc with camera'):
        device_tree.get_loc('Building 1 > Nested 3 (with camera)').delete()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Nested 4 (filler)': ['camera-2']},
            ],
        }

    with allure.step('Check loc schema remain unchanged after refresh'):
        device_tree.refresh()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Nested 4 (filler)': ['camera-2']},
            ],
        }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It should be possible to delete cameras from the locations")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_delete_camera_from_nested_location(client, metapix):
    create_location_schema_api(client, {
        'Building 1': [
            'camera-1',
            {'Cellar': ['camera-2']}
        ]
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()

    device_tree.get_bound_camera('Building 1 > camera-1').unbind()
    assert device_tree.loc_schema == {'▲ Building 1': [{'▲ Cellar': ['camera-2']}]}

    device_tree.get_bound_camera('Building 1 > Cellar > camera-2').unbind()
    assert device_tree.loc_schema == {'▲ Building 1': [{'Cellar': []}]}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Cameras in other locations are untouched if one of nested cameras was unbind')
@pytest.mark.usefixtures('teardown_delete_locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/device-manager/-/issues/95')
def test_device_tree_unbind_camera_from_one_loc(metapix, client):
    create_location_schema_api(client, {
        'Loc 1': ['camera-1'],
        'Loc 2': ['camera-2'],
        'Loc 3': ['camera-3'],
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()

    with allure.step('Unbind camera from loc and check other locations are untouched'):
        device_tree.get_bound_camera('Loc 2 > camera-2').unbind()
        assert device_tree.loc_schema == {'▲ Loc 1': ['camera-1'], 'Loc 2': [], '▲ Loc 3': ['camera-3']}

    metapix.refresh()
    assert device_tree.loc_schema == {'▲ Loc 1': ['camera-1'], 'Loc 2': [], '▲ Loc 3': ['camera-3']}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.tag('bug')
@allure.title("Location expands if there are found cameras")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1078")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1311')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_loc_expands_if_there_are_found_cameras(metapix, client):
    create_location_schema_api(client, {
        "Garden": [
            {"Enterance": ['camera-1']},
            'camera-2',
        ]
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()
    device_tree.get_loc('Garden > Enterance').collapse()
    assert device_tree.search_loc("camera-1"). \
        loc_schema == {
            '▲ Garden': [
                {'▲ Enterance': ['camera-1']},
            ]
        }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It should be possible to search for cameras")
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.usefixtures('teardown_disable_analytics_for_cameras')
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_rename_cameras')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
def test_device_tree_search_cameras(metapix, client):
    '''
    https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/602 (No 3)
    camera-1 is bound to location
    camera-2 is unassigned
    camera-3 is archived
    camera-4: attributes are changed (archived, inactive, enabled analytics)
    '''
    create_location_schema_api(client, {'Building 1': ['camera-1']})
    archive_cameras_by_name(client, 'camera-3')
    enable_camera(client, get_camera_by_name(client, 'camera-3'))
    camera4_data = get_camera_by_name(client, 'camera-4')
    archive_camera(client, camera4_data)
    change_analytics(client, camera4_data, 'face', True)

    test_data = [
        (
            'It is possible to search camera by name',
            "camera-3",
            {'Disabled': {'camera-3'}},
        ),
        (
            'It is possible to find several cameras by name',
            'camera',
            {'Location Not Specified': {'camera-2'}, 'Disabled': {'camera-3', 'camera-4'}},
        ),
        (
            'It is possible to find camera by its id',
            camera4_data.id,
            {'Disabled': {'camera-4'}},
        ),
        (
            'It is possible to find camera by enabled analytics',
            'faces',
            {'Disabled': {'camera-4'}},
        ),
        (
            'It is possible to find camera by active/inactive state',
            'plugin off',
            {'Disabled': {'camera-4'}},
        ),
        (
            'It is possible to find camera by archive state',
            'disabled',
            {'Disabled': {'camera-3', 'camera-4'}},
        ),
        ('Check empty result', 'deadbeef', NO_RESULTS),
    ]
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually(). \
        show_camera_info()

    for description, query, expected_cameras_schema, in test_data:
        with allure.step(description):
            assert device_tree.search_camera(query). \
                cameras_schema == expected_cameras_schema


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It should be possible to search for locations")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1145')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.usefixtures('teardown_disable_analytics_for_cameras')
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_rename_cameras')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
def test_device_tree_search_locations(metapix, client):
    ''' FYI https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/602 (No 4) '''
    camera4_data = get_camera_by_name(client, 'camera-4')
    disable_camera(client, camera4_data)
    change_analytics(client, camera4_data, 'face', True)
    test_data = [  # comment, query, expected_result, issue
        (
            'It is possible to search for nested location which contains bound camera',
            'Door 1',
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-3', 'camera-4']}]}]},
        ),
        (
            'Look for bound camera by name',
            'camera-4',
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-4']}]}]},
        ),
        (
            'Look for bound camera by id',
            camera4_data.id,
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-4']}]}]},
        ),
        (
            'All 3 locations are visible (including nested) when input has been cleared',
            '',
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-3', 'camera-4']}]}, 'camera-2'], 'Roof': []},
        ),
        (
            'Look for camera by its analytics',
            'faces',
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-4']}]}]},
        ),
        (
            'Look for camera by its active/inactive state',
            'plugin off',
            {'▲ Garden': [{'▲ Enterance': [{'▲ Door 1': ['camera-4']}]}]},
        ),
        ('When query does not match any camera/loc', 'deadbeef', NO_RESULTS),
    ]
    create_location_schema_api(
        client,
        {
            "Garden": [
                {
                    "Enterance": [
                        {"Door 1": ['camera-3', 'camera-4']}
                    ]
                },
                'camera-2',
            ],
            "Roof": [],
        }
    )
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually(). \
        show_camera_info()

    for comment, query, expected_result, in test_data:
        with allure.step(comment):
            log.info(comment)
            assert device_tree.search_loc(query). \
                loc_schema == expected_result


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("Disabling camera from device tree should work correctly")
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
def test_device_tree_inactive_camera(metapix, sender):
    disable_camera(sender.client, get_camera_by_name(sender.client, 'camera-4'))
    sender.clear_cache()
    device_tree = metapix.open_device_tree(). \
        show_camera_info()

    assert device_tree.unassigned_cameras.get("camera-4").is_active() is False


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("Cancel deleting location")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_cancel_deleting_location(metapix, client):
    create_location_schema_api(client, {"Root": []})
    device_tree = metapix.open_device_tree()

    with allure.step('Cancel deleting location "Root"'):
        device_tree.get_loc('Root').open_delete_dialog().cancel()

    with allure.step('Check location "Root" still exists'):
        assert device_tree.loc_schema == {'Root': []}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("Cancel archive/unarchive camera")
@pytest.mark.usefixtures('teardown_unarchive_cameras')
def test_cancel_archive_unarchive_camera(metapix, client):
    archive_cameras_by_name(client, 'camera-1')
    device_tree = metapix.open_device_tree()

    device_tree.unassigned_cameras.get("camera-2"). \
        open_archive_dialog().cancel()
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-2', 'camera-3', 'camera-4'},
        'Disabled': {'camera-1'}
    }

    device_tree.archived_cameras.get("camera-1"). \
        open_unarchive_dialog().cancel()
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-2', 'camera-3', 'camera-4'},
        'Disabled': {'camera-1'}
    }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.tag("bug")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/390")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/533")
@allure.title("It should be possible to archive camera bound to location (dialog disappears)")
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_dialog_disappears_if_archive_only_one_camera_bound_to_location(client, metapix):
    # TODO: review is required
    create_location_schema_api(client, {
        "loc-1": ["camera-1", "camera-2"]
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()
    try:
        device_tree.get_bound_camera('loc-1 > camera-1').archive()
    except ElementStillExistsException:
        pytest.fail("Appeared dialog 'Archive Camera' for another camera")
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-3', 'camera-4'},
        'Disabled': {'camera-1'}
    }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.link("https://gitlab.dev.metapixai.com/metapix-cloud/engine/meta-receiver/-/issues/17")
@allure.title("New objects should not arrive for the archived camera")
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_delete_layouts')
def test_new_objects_should_not_arrive_for_archived_camera(sender, metapix):
    sender.check_min_objects_count({'face': 1})
    widget = create_widget_api(metapix.dashboard, consts.WIDGET_VALUE, 'face')
    camera = get_camera_by_name(sender.client, 'camera-1')
    archive_camera(sender.client, camera)
    enable_camera(sender.client, camera)
    with pytest.raises(UnprocessableEntityException) as exception:
        sender.send('face-male', camera=camera.name, remember=False)
    assert 'Camera is archived' in str(exception)
    unarchive_camera(sender.client, camera)
    sender.wait_autorefresh_time()
    assert widget.objects_count == sender.objects_count('face')


@allure.epic("Backend")
@allure.title("Meta receiver must cause error you object is sent to disabled camera")
@pytest.mark.usefixtures('teardown_enable_cameras')
def test_meta_receiver_complains_of_disabled_camera(sender):
    ''' FYI: https://metapix-workspace.slack.com/archives/C03KM08QYTE/p1680773015254079 '''
    disable_camera(sender.client, get_camera_by_name(sender.client, 'camera-4'))
    sender.clear_cache()
    with pytest.raises(UnprocessableEntityException) as exception:
        sender.send('face-male', camera='camera-4', remember=False)
    assert 'Camera is not active' in str(exception.value)


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("It is not possible to bind one camera to two locations")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_only_one_loc_for_camera(metapix, client):
    # TODO: one more scenario: use mouse (drag and drop) to try to add an camera to another loc
    # TODO: review is required
    create_location_schema_api(client, {
        'Roof': ['camera-1'],
        'Cellar': ['camera-1'],
    })
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()
    assert device_tree.loc_schema == {'Roof': [], '▲ Cellar': ['camera-1']}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("Camera disappears from left list after adding to location")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_camera_disappears_from_unassigned_if_added_to_location(metapix, client):
    create_location_schema_api(client, {'Roof': []})
    device_tree = metapix.open_device_tree()
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-1', 'camera-2', 'camera-3', 'camera-4'}
    }

    # TODO: let's use drag and drop
    bind_camera_to_location_by_name(client, 'camera-1', 'Roof')
    device_tree.refresh()  # get rid of this refresh
    # TODO: check loc_schema after drag and drop
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-2', 'camera-3', 'camera-4'}
    }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("There is a caption in device three if no location has been added")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1069')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_no_locations_message(metapix, client):
    '''
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1333
    '''
    device_tree = metapix.open_device_tree()
    if (message := device_tree.locs_message) is None:
        pytest.fail('No message about there are no locs')
    else:
        assert message.startswith(
            'No Location Exists\n'
            'Currently you have not added any locations'
        )
    create_location_schema_api(client, {'root loc': []})
    metapix.refresh()
    assert device_tree.locs_message is None
    assert device_tree.loc_schema == {'root loc': []}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title("There is a caption in device three if no cameras has been added")
def test_device_tree_no_cameras_message(metapix, client, second_company):
    '''
    Lets use another company without cameras
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1333
    '''
    metapix.switch_company(). \
        select_by_name(second_company.name)
    delete_all_cameras_for_client(client)

    device_tree = metapix.open_device_tree()
    assert device_tree.cameras_message == NO_CAMERAS
    create_camera(client, 'camera-1')
    device_tree.refresh()
    assert device_tree.cameras_message is None
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-1'},
    }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.tag('bug')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1075')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1127')  # low priority
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1314')
@allure.title("After clearing the search field, cameras take on their real names")
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_cameras_after_clearing_location_search(metapix, client):
    expected_schema = {
        '▲ Garden':
        [
            {'▲ Enterance': [{'▲ Door 1': ['camera-1', 'camera-2']}]},
            'camera-3',
            'camera-4',
        ],
    }
    create_location_schema_api(client, expected_schema)
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()

    device_tree.search_loc('camera').search_loc('')
    assert device_tree.loc_schema == expected_schema

    device_tree.search_loc("deadbeed")
    assert device_tree.locs_message == 'No results\n' \
        'Not found any matches for search string'
    device_tree.input_search_location.clear_with_keyboard()
    assert device_tree.loc_schema == expected_schema


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1133')
@allure.title('Check clear button for "Search by cameras" works')
def test_device_search_by_camera_clear_button(metapix):
    device_tree = metapix.open_device_tree()
    device_tree.input_search_camera.type_text('hello')
    assert device_tree.cameras_schema == NO_RESULTS

    device_tree.input_search_camera.clear_with_button()
    assert device_tree.cameras_schema == {
        'Location Not Specified': {'camera-1', 'camera-2', 'camera-3', 'camera-4'},
    }


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1133')
@allure.title('Check clear button for "Search by location" works')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_search_by_locations_clear_button(metapix, client):
    create_location_schema_api(client, {
        "Enterance": ['camera-1', 'camera-2']
    })
    device_tree = metapix.open_device_tree()
    device_tree.input_search_location.type_text('hello')
    assert device_tree.loc_schema == NO_RESULTS

    device_tree.input_search_location.clear_with_button()
    assert device_tree.loc_schema == {'▼ Enterance': []}


@allure.epic("Frontend")
@allure.suite("Device Tree")
@allure.title('Check "Search by location" does not affect cameras state and vice versa')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
def test_device_location_and_cameras_search(metapix, client):
    create_location_schema_api(client, {
        'Building 1': [
            'camera-1',
            {'Cellar': ['camera-2']}
        ]
    })
    archive_cameras_by_name(client, 'camera-4')
    device_tree = metapix.open_device_tree(). \
        expand_all_locations_manually()

    with allure.step('Check locations search does not affect cameras state'):
        device_tree.search_loc('Hello')
        assert device_tree.cameras_schema == {
            'Location Not Specified': {'camera-3'},
            'Disabled': {'camera-4'},
        }
        device_tree.input_search_location.clear_with_keyboard()

    with allure.step('Check camera search does not affect locations state'):
        device_tree.search_camera('Hello')
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {
                    '▲ Cellar': ['camera-2'],
                },
                'camera-1',
            ]
        }


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('It should be possible to create location with "Create Location" button (the button is visible if there are no locations)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1316')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_create_location_button_ui(metapix):
    device_tree = metapix.open_device_tree()

    with allure.step('Check it is possible to create a new loc with "Create location" button'):
        device_tree.button_create_location.click()
        AddLocDialog(driver=metapix.driver). \
            set_values(name='Test loc'). \
            confirm()
        assert device_tree.loc_schema == {'Test loc': []}

    with allure.step('Check "Create location" button is not available any more'):
        assert is_element_exist(lambda: device_tree.button_create_location) is False


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Create loacation dialog input validation')
@pytest.mark.usefixtures('teardown_delete_locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1364')
def test_create_location_input_validation(metapix):
    ''' FYI https://metapix-workspace.slack.com/archives/C03KBMWC146/p1712746233845659 '''
    device_tree = metapix.open_device_tree()

    device_tree.button_create_location.click()
    add_loc_dialog = AddLocDialog(driver=metapix.driver)
    check_input_validation(
        # rules: more than 2, less than 100 chars, not empty
        control=add_loc_dialog.input_loc_name,
        valid=[
            '123',                   # more than 2
            ('1234567890'*10)[:-2],  # less than 100
        ],
        invalid=[
            'a',                      # less than 2
            '1234567890'*10 + 'abc',  # more than 1000
            '        '                # empty
        ],
        button=add_loc_dialog.button_confirm,
    )


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check camera attributes')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.usefixtures('teardown_disable_analytics_for_cameras')
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_rename_cameras')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.parametrize(
    'camera_name, camera_new_name', [
        ('camera-4', 'camera-4_new'),
    ],
    ids=('camera-4', ),
)
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
def test_device_tree_camera_attributes(metapix, client, camera_name, camera_new_name):
    ''' Task https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/602 (No 2) '''

    def check_attributes(camera, name, id, tags):
        assert camera.name == name
        assert camera.id == id
        assert camera.tags == tags

    def change_camera_attributes(camera_data):
        archive_camera(client, camera_data)
        change_analytics(client, camera_data, 'face', True)
        rename_camera(client, camera_data, camera_new_name)

    camera_data = get_camera_by_name(client, camera_name)

    with allure.step('Check camera attributes'):
        device_tree = metapix.open_device_tree(). \
            show_camera_info()
        check_attributes(
            device_tree.unassigned_cameras.get(camera_name),
            name=camera_name,
            id=camera_data.id,
            tags={'PLUGIN ON'},
        )

    with allure.step('Check changed camera attributes'):
        change_camera_attributes(camera_data)
        device_tree.refresh()
        check_attributes(
            device_tree.archived_cameras.get(camera_new_name),
            name=camera_new_name,
            id=camera_data.id,
            tags={'CAMERA DISABLED', 'PLUGIN OFF', 'FACES DETECTION'},
        )

    with allure.step('Check bound to location camera attributes'):
        unarchive_camera(client, camera_data)  # it is not possible to bind archived camera
        create_location_schema_api(client, {'Building 1': [camera_new_name]})
        device_tree.refresh(). \
            expand_all_locations_manually()
        check_attributes(
            device_tree.get_bound_camera(f'Building 1 > {camera_new_name}'),
            name=camera_new_name,
            id=camera_data.id,
            tags={'PLUGIN OFF', 'FACES DETECTION'},
        )


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Expand/collapse camera groups')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_delete_locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1335')
def test_device_tree_expand_collapse_cameras(metapix, client):
    '''
    FYI: saving the state of camera groups (spoilers) isn't supported
    https://metapix-workspace.slack.com/archives/C03KBMWC146/p1712908800726749
    # TODO: should expand/collapse state persist?
    '''
    archive_cameras_by_name(client, 'camera-4')
    create_location_schema_api(client, {
        'Building 1': [{'Cellar 1': []}, 'camera-1'],
        'Building 2': [{'Celalr 2': []}],
    })
    device_tree = metapix.open_device_tree()

    with allure.step('Collapse cameras'):
        device_tree.unassigned_cameras.collapse()
        assert device_tree.cameras_schema == {'Location Not Specified': 'COLLAPSED', 'Disabled': {'camera-4'}}
        device_tree.archived_cameras.collapse()
        assert device_tree.cameras_schema == {'Location Not Specified': 'COLLAPSED', 'Disabled': 'COLLAPSED'}

    with allure.step('Expand cameras'):
        device_tree.unassigned_cameras.expand()
        assert device_tree.cameras_schema == {'Location Not Specified': {'camera-2', 'camera-3'}, 'Disabled': 'COLLAPSED'}
        device_tree.archived_cameras.expand()
        assert device_tree.cameras_schema == {'Location Not Specified': {'camera-2', 'camera-3'}, 'Disabled': {'camera-4'}}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Expand/collapse locations')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_expand_collapse_locs(metapix, client):
    create_location_schema_api(client, {
        'Building 1': [{'Cellar 1': ['camera-2']}, 'camera-1'],
        'Building 2': [{'Celalr 2': []}],
    })
    device_tree = metapix.open_device_tree()

    with allure.step('Expand/Collapse location'):
        device_tree.get_loc('Building 1').expand()
        assert device_tree.loc_schema == {
            '▲ Building 1': [{'▼ Cellar 1': []}, 'camera-1'],
            '▼ Building 2': [],
        }

        device_tree.get_loc('Building 1 > Cellar 1').expand()
        assert device_tree.loc_schema == {
            '▲ Building 1': [{'▲ Cellar 1': ['camera-2']}, 'camera-1'],
            '▼ Building 2': [],
        }

        device_tree.refresh()
        assert device_tree.loc_schema == {
            '▲ Building 1': [{'▲ Cellar 1': ['camera-2']}, 'camera-1'],
            '▼ Building 2': [],
        }


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Expand/collapse all locations with buttons in header')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_expand_collapse_all_locs_with_header_buttons(metapix, client):
    create_location_schema_api(client, {
        'Building 1': [{'Cellar 1': ['camera-2']}, 'camera-1'],
        'Building 2': [{'Celalr 2': []}],
    })
    device_tree = metapix.open_device_tree()

    with allure.step('"Expand all" button'):
        device_tree.expand_all_locations()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Cellar 1': ['camera-2']},
                'camera-1',
            ],
            '▲ Building 2': [
                {'Celalr 2': []},
            ],
        }

        device_tree.refresh()
        assert device_tree.loc_schema == {
            '▲ Building 1': [
                {'▲ Cellar 1': ['camera-2']},
                'camera-1',
            ],
            '▲ Building 2': [
                {'Celalr 2': []},
            ],
        }

    with allure.step('"Collapse all" button'):
        device_tree.collapse_all_locations()
        assert device_tree.loc_schema == {'▼ Building 1': [], '▼ Building 2': []}

        device_tree.refresh()
        assert device_tree.loc_schema == {'▼ Building 1': [], '▼ Building 2': []}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('The button state must match with locations state')
@pytest.mark.usefixtures('teardown_delete_locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1341')
def test_location_button_state_is_correct(metapix, client):
    create_location_schema_api(client, {
        'loc 1': ['camera-1', 'camera-2'],
        'loc 2': ['camera-3'],
    })
    device_tree = metapix.open_device_tree()

    with allure.step('Check button state after opening device tree is "Open all locations"'):
        assert device_tree.get_location_expanding_button_state() == 'Open all locations'
        assert device_tree.loc_schema == {'▼ loc 1': [], '▼ loc 2': []}

    with allure.step('Check button state after expanding all locations changes to "Close all locations"'):
        device_tree.expand_all_locations()
        assert device_tree.get_location_expanding_button_state() == 'Close all locations'
        assert device_tree.loc_schema == {'▲ loc 1': ['camera-1', 'camera-2'], '▲ loc 2': ['camera-3']}

    with allure.step('Check button state is correct after refreshing the page'):
        metapix.refresh()
        assert device_tree.get_location_expanding_button_state() == 'Close all locations'
        assert device_tree.loc_schema == {'▲ loc 1': ['camera-1', 'camera-2'], '▲ loc 2': ['camera-3']}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Search is not being reset after drag and drop camera')
@allure.tag('bug')
@pytest.mark.usefixtures('teardown_delete_locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1132')
def test_device_tree_check_search_after_drag_and_drop_camera(metapix, client):
    create_location_schema_api(client, {'Loc 1': ['camera-1']})
    device_tree = metapix.open_device_tree()

    device_tree.search_camera('camera')
    device_tree.unassigned_cameras.get('camera-2'). \
        drag_and_drop(device_tree.get_loc('Loc 1'))

    with allure.step('Check camera search state remains unchanged'):
        assert device_tree.input_search_camera.value == 'camera'
        assert device_tree.cameras_schema == {'Location Not Specified': {'camera-3', 'camera-4'}}
        assert device_tree.loc_schema == {'▲ Loc 1': ['camera-1', 'camera-2']}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Search field should not have cross button in case it is empty')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1354')
def test_cross_button_if_input_is_empty(metapix):
    # this feature is concerned not only with "device tree" feature
    def check_input(control: Input_v0_48_4):
        with allure.step('There is no "cross button" by default'):
            assert not has_clear_button(control)

        with allure.step('"Cross button" appears in case there is any text'):
            control.type_text('hello')
            assert has_clear_button(control)

        with allure.step('"Cross button" disappears after clearing the input with keyboard'):
            control.clear_with_keyboard()
            assert not has_clear_button(control)

        with allure.step('"Cross button" disappears after clearing the input with "cross button"'):
            control.type_text('hello')
            control.clear_with_button()
            assert not has_clear_button(control)

    device_tree = metapix.open_device_tree()
    check_input(device_tree.input_search_camera)


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Search loc: two root locs have the same name')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1386')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_search_two_root_locs_with_same_name(metapix, client):
    with allure.step('Create required locations'):
        create_location_schema_api(client, {
            'test': {'search test': []},
        })
        device_tree = metapix.open_device_tree()
        with suppress(UndefinedElementException):
            device_tree.add_root_loc('test')

    device_tree.search_loc('search')
    assert [loc.name for loc in device_tree._get_root_locs()] == ['test']
    assert device_tree.loc_schema == {'▲ test': [{'search test': []}]}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('All identically named cameras are returned in search by locations')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1398')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_device_tree_search_identically_named_cameras(metapix, client, create_temporary_camera):
    create_location_schema_api(client, {
        'loc-1': ['camera-4'],
        'loc-2': [],
    })
    camera_4_temp = create_temporary_camera('camera-4')
    bind_camera_to_location_by_id(client, camera_4_temp.id, 'loc-2')  # use camera id to avoid name collision
    device_tree = metapix.open_device_tree()
    device_tree.search_loc('camera-4')
    assert device_tree.loc_schema == {'▲ loc-1': ['camera-4'], '▲ loc-2': ['camera-4']}


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Camera name does fit during archiving/unarchiving')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1396')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.parametrize('name', ['camera with very very long name'])
def test_archive_camera_with_long_name(metapix, create_temporary_camera, name):
    def check_name_in_dialog(dialog):
        assert name in dialog.message
        dialog.confirm()

    create_temporary_camera(name)
    device_tree = metapix.open_device_tree()

    check_name_in_dialog(device_tree.unassigned_cameras.get(name).open_archive_dialog())
    check_name_in_dialog(device_tree.archived_cameras.get(name).open_unarchive_dialog())


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check camera highlighting during search (in case camera name has several identical letters)')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1414')
@pytest.mark.parametrize('name,queries', [
    ('bbbbbbbbbbbbbbbbbb', ['b', 'bbb']),
])
def test_camera_search_highlighting_identical_letters(metapix, create_temporary_camera, name, queries):
    create_temporary_camera(name)
    device_tree = metapix.open_device_tree()
    camera = device_tree.unassigned_cameras.get(name)
    assert camera.highlighted_name is None
    for query in queries:
        with allure.step(f'Check camera highlighted name for query "{query}"'):
            device_tree.search_camera(query)
            assert camera.highlighted_name == query


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Archived camera becomes disabled')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/device-manager/-/issues/104')
@pytest.mark.parametrize('camera_name', ['camera-3'])
@pytest.mark.usefixtures('teardown_unarchive_cameras')
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
def test_device_tree_archived_camera_becomes_disabled(metapix, client, camera_name):
    archive_cameras_by_name(client, camera_name)
    device_tree = metapix.open_device_tree(). \
        show_camera_info()
    device_tree.archived_cameras.get(camera_name).unarchive()
    assert device_tree.unassigned_cameras.get(camera_name).is_active() is False


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check location description')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.parametrize('name,description,new_description', [
    ('loc-1', 'test description', 'changed description'),
])
def test_device_tree_loc_description(metapix, name, description, new_description):
    def assert_description_tooltip(loc, expected_tooltip: str):
        actual_tooltip = loc.get_description_tooltip()
        with allure.step(f'{loc} check tooltip "{actual_tooltip=}" vs "{expected_tooltip}"'):
            log.info(f'{loc} check tooltip "{actual_tooltip=}" vs "{expected_tooltip}"')
            assert actual_tooltip.lower() == f'description\n{expected_tooltip}'.lower()

    device_tree = metapix.open_device_tree()

    with allure.step('Check description: create location'):
        device_tree.add_root_loc(name=name, description=description)
        loc = device_tree.get_loc(name)
        assert_description_tooltip(loc, description)

    with allure.step('Check description: edit location'):
        edit_dialog = loc.open_edit_dialog()
        assert edit_dialog.input_loc_description.value == description
        edit_dialog.input_loc_description.type_text(new_description, clear_with_keyboard=True)
        edit_dialog.confirm()
        assert_description_tooltip(loc, new_description)

    with allure.step('Check description: refresh'):
        device_tree.refresh()
        assert_description_tooltip(device_tree.get_loc(name), new_description)


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check it is possible to delete camera')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1498')
@pytest.mark.parametrize('camera_name', ['temp-camera'])
def test_device_tree_delete_camera_permanently(
        metapix: RootPage, create_temporary_camera: Callable[[str], CameraData], camera_name: str):
    def get_channels_in_use() -> int:
        licenses_page = metapix.open_settings(). \
            open_licenses()
        text = licenses_page.licenses_summary.splitlines()[-1]
        amount = int(text.split()[0])
        metapix.open_device_tree()
        return amount

    create_temporary_camera(camera_name)
    device_tree = metapix.open_device_tree()
    assert get_channels_in_use() == 5

    with allure.step('Check delete camera dialog'):
        delete_camera_dialog = device_tree.unassigned_cameras.get(camera_name). \
            open_delete_dialog()
        assert delete_camera_dialog.message == f'Are you sure you want to delete the camera named "{camera_name}" ?\n\n ' \
            'Please disable the plugin for this camera in the Video Management Platform before proceeding.\n ' \
            'Note that deleting this camera will also remove all objects detected by it'

    with allure.step('Close delete camera dialog does not have any effect'):
        delete_camera_dialog.cancel()
        assert device_tree.cameras_schema == {'Location Not Specified': {'camera-1', 'camera-3', 'camera-4', camera_name, 'camera-2'}}

    with allure.step('It is possible to delete camera'):
        device_tree.unassigned_cameras.get(camera_name). \
            open_delete_dialog(). \
            confirm()
        assert device_tree.cameras_schema == {'Location Not Specified': {'camera-1', 'camera-3', 'camera-4', 'camera-2'}}
        assert get_channels_in_use() == 4


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Add camera to location via loc menu')
@pytest.mark.usefixtures('teardown_delete_locations')
@pytest.mark.usefixtures('teardown_enable_cameras')
@pytest.mark.usefixtures('teardown_unarchive_cameras')
def test_device_tree_add_camera_to_loc(metapix: RootPage, client: ApiClient):
    '''
    QA task: https://gitlab.dev.metapixai.com/metapix-cloud/Tests/-/issues/636
    FYI (discussion concerning adding disabled camera): https://metapix-workspace.slack.com/archives/C03KBMWC146/p1728297589173019
    '''
    with allure.step('Prepare data'):
        create_location_schema_api(
            client,
            {
                'loc-1': ['camera-1'],
                'loc-2': ['camera-2'],
            }
        )
        archive_cameras_by_name(client, 'camera-4')
        device_tree = metapix.open_device_tree(). \
            expand_all_locations_manually()

    with allure.step('Add "camera-3" and "camera-4" to loc-1 via location menu'):
        add_cam_dialog = device_tree.get_loc('loc-1'). \
            open_add_cameras_dialog()
        assert add_cam_dialog.schema == ['camera-3 ☐', 'camera-4 ☐']
        add_cam_dialog.select_cameras('camera-3', 'camera-4'). \
            confirm()
        assert device_tree.loc_schema == {'▲ loc-1': ['camera-1', 'camera-3', 'camera-4'], '▲ loc-2': ['camera-2']}
        assert device_tree.cameras_schema == 'No unassigned cameras'


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check state of hide/show camera is saves')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1532')
@pytest.mark.usefixtures('teardown_restore_default_camera_info_state')
@pytest.mark.usefixtures('teardown_delete_locations')
def test_button_cemera_info_save_state(metapix: RootPage, client: ApiClient):
    with allure.step('Prepare cameras for test'):
        create_location_schema_api(client, {
            'Location 1': ['camera-1'],
        })
    with allure.step('Open device tree and show cameras info'):
        device_tree = metapix.open_device_tree()
        device_tree.show_camera_info()
        device_tree.expand_all_locations()

    with allure.step('Check bounded camera has tags'):
        assert camera_info_displayed(device_tree, 'Location 1 > camera-1')

    with allure.step('Check that all cameras have tags'):
        assert camera_info_displayed(device_tree)

    with allure.step('Refresh page and check camera info state'):
        metapix.refresh()
        assert camera_info_displayed(device_tree)

    with allure.step('Hide cameras info and check that all tags are disappeared'):
        device_tree.hide_camera_info()
        assert not camera_info_displayed(device_tree)
