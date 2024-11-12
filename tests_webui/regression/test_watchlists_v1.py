import logging
from functools import partial

import allure
import pytest

import consts
from tools.client import ApiClient
from tools.watchlists import add_predicates
from tools.watchlists import create_face_predicates
from tools.watchlists import create_vehicle_predicates
from tools.watchlists import create_watchlist

from pages.base_page import ElementStillExistsException
from pages.base_page import is_element_exist
from pages.root import RootPage
from pages.watchlists.watchlists import ALL_CLUSTERS
from pages.watchlists.watchlists import CLUSTER_NAME

from tests_webui.regression import check_pagination

pytestmark = [
    pytest.mark.regression,
]

log = logging.getLogger(__name__)


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("It is possible to create watchlist for {base}")
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize(
    'name,base,filters,expected_schema',
    [
        (
            'wl_1',
            'face',
            consts.FILTER_MALE | {consts.FILTER_AGE: (10, 90)} | {consts.FILTER_OBJECTS_NAME: 'object_name'},
            [{CLUSTER_NAME: 'object_name', 'Age': '10-90', 'Gender': 'Male'}],
        ),
        (
            'wl_1',
            'vehicle',
            consts.FILTER_SEDAN | {consts.FILTER_LICENSE_PLATE: '1234'},
            [{'Vehicle License Plate': '1234', 'Vehicle Type': 'Sedan'}],
        ),
    ],
    ids=('face', 'vehicle')
)
def test_create_watchlist_ui(metapix, name, base, filters, expected_schema):
    watchlists = metapix.open_watchlists()

    with allure.step('There are two bases available: face and vehicle'):
        add_dialog = watchlists.open_add_dialog()
        add_dialog.set_name(name)
        add_dialog.dropdown_base.expand()
        assert add_dialog.dropdown_base.options == {'Face', 'Vehicle'}
        add_dialog.dropdown_base._select_option(base)

    with allure.step(f'It is possible to set all possible filters for {base}'):
        add_dialog.set_filters(filters)

    with allure.step('Information about successful creation of watch list is displayed'):
        success_dialog = add_dialog.confirm()
        assert success_dialog.message.startswith('Success\nWatch List has been created')

    with allure.step('The filters what had been set are displayed'):
        filters_table = success_dialog.close()
        assert filters_table.schema == expected_schema


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("It is not possible to create watchlist with existing name")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1395')
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize(
    'name,base,filters',
    [
        (
            'wl_1',
            'vehicle',
            consts.FILTER_VEHICLE | consts.FILTER_SEDAN | {consts.FILTER_LICENSE_PLATE: '1234'},
        ),
    ],
)
def test_creating_watchlist_with_existing_name_is_not_allowed(metapix, client, name, base, filters):
    create_watchlist(client, name, base)
    watchlists = metapix.open_watchlists()
    with allure.step('It is not possible to add watchlist with existing name'):
        add_dialog = watchlists.open_add_dialog()
        add_dialog.set_name(name)
        add_dialog.set_filters(filters)
        add_dialog.confirm(wait_disappeared=False)
        metapix.assert_tooltip('Error: The name is already in use. Please set a new one')
        with pytest.raises(ElementStillExistsException):
            add_dialog.wait_disappeared()

    with allure.step('Check no new entities appeared in watchlists table'):
        metapix.refresh()
        assert watchlists.schema == [{'Object Type': base.capitalize(), 'Watchlist Name': name}]


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("It is not possible to create watchlist with default filters")
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1320')
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize(
    'base,filters_data', [
        ('face', [
            (consts.FILTER_OBJECTS_NAME, 'test', ''),
            (consts.FILTER_AGE, (10, 50), (0, 100)),
            (consts.FILTER_GENDER, consts.GENDER_FEMALE, consts.OPTION_ALL),
        ]),
        ('vehicle', [
            (consts.FILTER_VEHICLE_TYPE, consts.VEHICLE_TYPE_SEDAN, consts.OPTION_ALL),
            (consts.FILTER_LICENSE_PLATE, '1234', ''),
        ]),
    ],
    ids=('face', 'vehicle'),
)
def test_creating_watchlist_with_default_filters_is_not_allowed(metapix, base, filters_data):
    watchlists = metapix.open_watchlists()
    with allure.step('Check "Submit" button is disabled by default'):
        add_dialog = watchlists.open_add_dialog()
        add_dialog.set_filters({consts.FILTER_WATCHLIST_NAME: 'wl1'} | {consts.FILTER_OBJECT_TYPE: base.upper()})
        assert add_dialog.button_confirm.is_active() is False
    for filter_name, new_value, default_value in filters_data:
        with allure.step(f'Check it is possible to submit if filter "{filter_name}" has been set'):
            add_dialog.set_filters({filter_name: new_value})
            assert add_dialog.button_confirm.is_active() is True

        with allure.step(f'Check it is not possible to submit if filter "{filter_name}" has been reseted to default value'):
            add_dialog.set_filters({filter_name: default_value})
            assert add_dialog.button_confirm.is_active() is False


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("Check deleting watchlist")
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize('name', ['wl0'])
def test_delete_watchlist(metapix, client, name):
    create_watchlist(client, name, 'face')
    watchlists = metapix.open_watchlists()
    wl = watchlists.get(name)

    with allure.step('Check "Close" button of "Delete watchlist" dialog'):
        wl.open_delete_dialog(). \
            close()
        assert watchlists.schema == [{'Watchlist Name': name, 'Object Type': 'Face'}]

    with allure.step('Check cancelling "Delete watchlist" dialog (clicking by crosshair in header)'):
        wl.open_delete_dialog(). \
            cancel()
        assert watchlists.schema == [{'Watchlist Name': name, 'Object Type': 'Face'}]

    with allure.step('Check "Submit" button of "Delete watchlist" dialog'):
        wl.open_delete_dialog(). \
            confirm(). \
            close()   # close success dialog
        assert watchlists.schema == 'No Watch Lists\nWatch Lists are used to monitor and track specific objects with predefined filters'


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("Check deleting filters")
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize('name', ['wl0'])
def test_delete_filters(metapix, client, name):
    wl = create_watchlist(client, name, 'face')
    add_predicates(client, wl, create_face_predicates(age=(10, 20)))
    add_predicates(client, wl, create_face_predicates(cluster_name='test name'))
    filters_table = metapix.open_watchlists(). \
        get(name).open_filters()

    with allure.step('Check "Cancel" button for "Delete Filter" dialog'):
        filters_table.get(ix=0). \
            open_delete_dialog(). \
            cancel()
        assert filters_table.schema == [
            {CLUSTER_NAME: ALL_CLUSTERS, 'Age': '10-20', 'Gender': 'All genders'},
            {CLUSTER_NAME: 'test name', 'Age': 'All ages', 'Gender': 'All genders'},
        ]

    with allure.step('Check X (crosshair icon) for "Delete Filter" dialog'):
        filters_table.get(ix=0). \
            open_delete_dialog(). \
            close()
        assert filters_table.schema == [
            {CLUSTER_NAME: ALL_CLUSTERS, 'Age': '10-20', 'Gender': 'All genders'},
            {CLUSTER_NAME: 'test name', 'Age': 'All ages', 'Gender': 'All genders'},
        ]

    with allure.step('Check it is possible to delete a filter'):
        filters_table.get(cluster_name='test name'). \
            open_delete_dialog(). \
            confirm(). \
            close()
        assert filters_table.schema == [
            {CLUSTER_NAME: ALL_CLUSTERS, 'Age': '10-20', 'Gender': 'All genders'},
        ]

    with allure.step('Check there is a correcponding caption and "Add Filter" button (in case there are no filters)'):
        filters_table.get(ix=0). \
            delete()
        assert filters_table.schema == 'No Filters\nCurrently you do not have added any filters'
        assert is_element_exist(lambda: filters_table.button_add) is True


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title("It is possible to edit watchlist")
@pytest.mark.usefixtures('teardown_delete_watchlists')
@pytest.mark.parametrize('name,new_name', [('wl0', 'wl0_new')])
@pytest.mark.parametrize('base', ['face', 'vehicle'])
def test_edit_watchlist(metapix, client, base, name, new_name):
    create_watchlist(client, name, base)
    watchlists = metapix.open_watchlists()

    with allure.step(f'Check changing name: {name} -> {new_name}'):
        wl = watchlists.get(name)
        wl.edit(name=new_name)
        assert watchlists.schema == [
            {'Object Type': base.capitalize(), 'Watchlist Name': new_name}
        ]


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Check "Submit" button is not active in case required parameters have wrong value')
@pytest.mark.parametrize('right_name,wrong_name,filters', [
    ('wl0', 'wl!', consts.FILTER_VEHICLE | {consts.FILTER_LICENSE_PLATE: '1234'}),
])
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_create_watchlist_submit_button(metapix, right_name, wrong_name, filters):
    add_dialog = metapix.open_watchlists(). \
        open_add_dialog()

    with allure.step('Check "Submit" button: no object type'):
        add_dialog.set_filters({consts.FILTER_WATCHLIST_NAME: right_name})
        assert add_dialog.button_confirm.is_active() is False

    with allure.step('Check "Submit" button: no object name'):
        add_dialog.set_filters({consts.FILTER_WATCHLIST_NAME: ''} | filters)
        assert add_dialog.button_confirm.is_active() is False

    with allure.step('Check "Submit" button: cluster name and object type are correct'):
        add_dialog.set_filters({consts.FILTER_WATCHLIST_NAME: right_name} | filters, ignore_already_selected=True)
        assert add_dialog.button_confirm.is_active() is True

    with allure.step('Check "Submit" button: cluster name has invalid value'):
        add_dialog.set_filters({consts.FILTER_WATCHLIST_NAME: wrong_name} | filters, ignore_already_selected=True)
        assert add_dialog.button_confirm.is_active() is False


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Check default filter values are displayed correctly')
@pytest.mark.parametrize(
    'base,create_predicates_functions,expected_schema',
    [
        (
            'face',
            [
                partial(create_face_predicates, age=(10, 20)),
                partial(create_face_predicates, gender='male'),
                partial(create_face_predicates, cluster_name='test name'),
            ],
            [
                {CLUSTER_NAME: ALL_CLUSTERS, 'Age': '10-20', 'Gender': 'All genders'},
                {CLUSTER_NAME: ALL_CLUSTERS, 'Age': 'All ages', 'Gender': 'Male'},
                {CLUSTER_NAME: 'test name', 'Age': 'All ages', 'Gender': 'All genders'},
            ],
        ),
        (
            'vehicle',
            [
                partial(create_vehicle_predicates, license_plate='123'),
                partial(create_vehicle_predicates, vehicle_type='Cab'),
            ],
            [
                {'Vehicle Type': 'All vehicles types', 'Vehicle License Plate': '123'},
                {'Vehicle Type': 'Cab', 'Vehicle License Plate': 'All license plates'},
            ]
        ),
    ],
    ids=('face', 'vehicle')
)
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_watchlist_filters_default_values(metapix, client, base, create_predicates_functions, expected_schema):
    wl = create_watchlist(client, 'wl', base)

    with allure.step(f'Create filters for {wl}'):
        for func in create_predicates_functions:
            add_predicates(client, wl, func())

    with allure.step('Check filters schama'):
        filters = metapix.open_watchlists(). \
            get('wl').open_filters()
        assert filters.schema == expected_schema


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Check watchlist pagination')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_watchlist_pagination(metapix, client):
    for ix in range(12):
        create_watchlist(client, f'wl_{ix}', 'face')
    watchlists = metapix.open_watchlists()
    check_pagination(watchlists, fields=['Watchlist Name'])


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Check watchlist filters pagination')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_watchlist_filters_pagination(metapix, client):
    wl = create_watchlist(client, 'wl', 'face')
    for ix in range(12):
        add_predicates(client, wl, create_face_predicates(age=(ix, 100)))
    filters = metapix.open_watchlists(). \
        get('wl'). \
        open_filters()
    check_pagination(filters, fields=['Age'])


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Check editing watchlist filters')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_edit_filters_watchlist(metapix, client):
    wl = create_watchlist(client, 'wl', 'face')
    add_predicates(client, wl, create_face_predicates(gender='male'))
    add_predicates(client, wl, create_face_predicates(cluster_name='test_name', age=(10, 90), gender='male'))

    filters = metapix.open_watchlists(). \
        get('wl'). \
        open_filters()

    filters.get(cluster_name='test_name'). \
        edit(consts.FILTER_FEMALE)
    assert filters.schema == [
        {'Age': 'All ages', 'Gender': 'Male', CLUSTER_NAME: ALL_CLUSTERS},
        {'Age': '10-90', 'Gender': 'Female', CLUSTER_NAME: 'test_name'},
    ]

    filters.refresh()
    assert filters.schema == [
        {'Age': 'All ages', 'Gender': 'Male', CLUSTER_NAME: ALL_CLUSTERS},
        {'Age': '10-90', 'Gender': 'Female', CLUSTER_NAME: 'test_name'},
    ]


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('The "SUBMIT" button is active, when no changes are done to the filters')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1470')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_edit_filters_submit_button_state(
        metapix: RootPage, client: ApiClient):
    with allure.step('Prepare data'):
        wl = create_watchlist(client, 'wl', 'face')
        add_predicates(client, wl, create_face_predicates(gender='male'))
        filters = metapix.open_watchlists(). \
            get('wl').open_filters()

    with allure.step('Open edit filter dialog and check "Submit" button is disabled by default'):
        edit_filter_dialog = filters.get(ix=0).open_edit_dialog()
        assert edit_filter_dialog.button_confirm.is_active() is False

    with allure.step('Change Gender Male -> Female and check "Submit" button becomes enabled'):
        edit_filter_dialog.set_filters(consts.FILTER_FEMALE)
        assert edit_filter_dialog.button_confirm.is_active() is True

    with allure.step('Revert gender (Female -> Male) and check "Submit" button becomes disabled again'):
        edit_filter_dialog.set_filters(consts.FILTER_MALE)
        assert edit_filter_dialog.button_confirm.is_active() is False


@allure.epic('Frontend')
@allure.suite('Watch Lists')
@allure.story('Watch Lists')
@allure.title('Pagination: there is redirect to previous page if current page is empty')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1599')
@pytest.mark.usefixtures('teardown_delete_watchlists')
def test_pagination_redirect_from_empty_page_to_previous_page(
        metapix: RootPage, client: ApiClient):
    ''' This test isn't about watchlists but pagination '''
    with allure.step('Prepare data'):
        wl = create_watchlist(client, 'wl', 'face')
        for ix in range(11):
            add_predicates(client, wl, create_face_predicates(age=(ix, 100)))
        filters = metapix.open_watchlists(). \
            get('wl'). \
            open_filters()

    with allure.step('Go to the last page'):
        filters.pages.get_next()
        assert filters.pages.schema == {'first': 11, 'last': 11, 'total': 11}

    with allure.step('Delete the last filter on the last page'):
        filters.get(ix=0). \
            delete()
        with allure.step('Make sure we have been redirected to previous page'):
            assert filters.pages.schema == {'first': 1, 'last': 10, 'total': 10}
