import logging

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def sender(sender):
    # TODO: add pytest option to send these objects
    # conditions = {type_: 1 for type_ in ('face-bad-quality',
    #                                      'person-bad-quality',
    #                                      'vehicle-bad-quality',
    #                                      'vehicle-type-unknown')
    #               }
    # with allure.step('Sending problematic objects'):
    #     log.info('Sending problematic objects')
    #     sender.check_min_objects_count(conditions, cameras="camera-1")
    #     sender.check_min_objects_count(conditions, cameras="camera-2")
    return sender


@pytest.fixture(scope='function', autouse=True)
def teardown_delete_layouts(teardown_delete_layouts):
    ''' Make this fixture autousable for all widget suites '''
