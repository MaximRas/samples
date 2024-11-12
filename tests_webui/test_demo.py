from contextlib import suppress
from typing import Generator
import logging

import allure
import pytest

from tools import RequestStatusCodeException
from tools.cameras import NoMoreLicensesAvailable
from tools.cameras import enable_camera
from tools.cameras import get_camera_by_name
from tools.client import ApiClient
from tools.image_sender import ImageSender
from tools.licenses import request_demo_license
from tools.steps import prepare_cameras_for_suite
from tools.time_tools import now_pst
from tools.time_tools import parse_date

from pages.root import RootPage

log = logging.getLogger(__name__)


@pytest.fixture
def teardown_request_demo(client: ApiClient) -> Generator[None, None, None]:
    yield
    with allure.step(f'{client}: request demo'):
        log.info(f'{client}: request demo')
        with suppress(RequestStatusCodeException):
            request_demo_license(client)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('It should be possible to request Demo license')
@pytest.mark.usefixtures('teardown_request_demo')
@pytest.mark.usefixtures('teardown_enable_cameras')
def test_request_demo(metapix: RootPage, sender: ImageSender):
    try:
        camera = prepare_cameras_for_suite(sender.client, count=4)[-1]
        # TODO: behavior has changed: it isn't possible to create any camera if there is no lic
    except NoMoreLicensesAvailable:
        camera = get_camera_by_name(sender.client, 'camera-4')

    with pytest.raises(NoMoreLicensesAvailable):
        enable_camera(sender.client, camera)

    licenses_page = metapix.open_settings(). \
        open_licenses()
    assert licenses_page.schema == []

    licenses_page.activate_demo_license()
    metapix.assert_no_error_tooltips()
    assert licenses_page.licenses, 'There are no licenses'
    assert licenses_page.schema == [
        {
            "days": 30,
            "cameras": 30,
            "key": licenses_page.licenses[0].key,
        }
    ]
    assert parse_date(licenses_page.licenses[-1].expires_at) > now_pst()
    assert enable_camera(sender.client, camera).active is True
