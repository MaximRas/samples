import pytest

import consts
from tools.steps import prepare_cameras_for_suite
from tools.search import search_api_v2
from tools.types import EmailType
from tools.gitlab_integration import raise_if_fixed


@pytest.fixture(scope='function', autouse=True)
def cameras(client):
    return prepare_cameras_for_suite(client, count=1)


def check_meta(sender, object_type, meta):
    sender.send(object_type)
    assert sender._objects[-1].has_meta(meta), f"{object_type} doesn't match meta: {meta}"


@pytest.mark.parametrize(
    'template,meta',
    [
        ('face-female', consts.META_FEMALE),
        ('face-good-quality', consts.META_GOOD_QUALITY),
        ('face-male', consts.META_MALE),
        ('person-good-quality', consts.META_GOOD_QUALITY),
        ('vehicle-good-quality', consts.META_GOOD_QUALITY),
        ('vehicle-type-hatchback', consts.META_HATCHBACK),
        ('vehicle-type-minivan', consts.META_MINIVAN),
        ('vehicle-type-sedan', consts.META_SEDAN),
        ('vehicle-type-truck', consts.META_TRUCK),
        ('vehicle-type-van', consts.META_VAN),
        ('vehicle-type-wagon', consts.META_WAGON),
        ('vehicle-type-suv', consts.META_SUV),
        ('vehicle-type-unknown', consts.META_UNKNOWN_VEHICLE),
        ('face-bad-quality', consts.META_BAD_QUALITY),
        ('person-bad-quality', consts.META_BAD_QUALITY),
        ('vehicle-bad-quality', consts.META_BAD_QUALITY),
    ], ids=lambda val: val if isinstance(val, str) else 'meta',
)
def test_base_images_meta(sender, template, meta):
    # TODO: check face-30-age and face-70-age
    check_meta(sender, template, meta)


def test_it_is_possible_to_send_bad_quality_objects(sender):
    pass


def test_is_clusterization_works(sender):
    pass


def test_clickhouse_objects_arrive_speed(sender):
    pass


def test_clusterization_speed(sender):
    pass


@pytest.mark.parametrize('base', ['face'])
def test_open_object(metapix, sender, base):
    sender.check_min_objects_count({base: 1}, timeslice=None)
    metapix.open_object(search_api_v2(sender.client, base).get_first().id)


def test_open_users(metapix, client):
    metapix.open_settings().open_users(client)


def test_email_type():
    assert EmailType('vbelyaev@metapix.ai') == EmailType('VBelyaev@metapix.ai')
    assert EmailType('vbelyaev@metapix.ai') != EmailType('dpetrov@metapix.ai')


@pytest.mark.parametrize(
    'issue',
    [
        'engine/http-api/object-management/object-manager/-/issues/352',
    ]
)
def test_check_issue_is_fixed(issue):
    raise_if_fixed(issue)
