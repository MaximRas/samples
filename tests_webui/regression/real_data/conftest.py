import logging

import pytest

from tools.layouts import delete_layout
from tools.layouts import get_layouts

log = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def client(client_spc):
    return client_spc


@pytest.fixture(scope='function')
def sender():
    # It is not allowed
    raise NotImplementedError


@pytest.fixture(scope='function')
def cameras():
    pass


@pytest.fixture(scope='module')
def use_search_during_choosing_company():
    return True


@pytest.fixture(scope='function', autouse=True)
def teardown_delete_layouts(client):
    yield
    default_has_been_found = False
    for layout in get_layouts(client):
        if default_has_been_found is False and layout.shared is False:
            default_has_been_found = True
            log.info(f"Skip layout: {layout}")
        else:
            delete_layout(client, layout)
