import logging
from collections import Counter

import allure

import consts
from pages.grid_items import GridItemsPage
from pages.widgets.base_widget import BaseWidget

log = logging.getLogger(__name__)


class LiveFeedOverflowException(Exception):
    '''Has more that maximum objects (32)'''


class LiveFeedDuplicateObjects(Exception):
    pass


def check_uniq_ids(widget):
    '''
    FYI:
    - https://metapix-workspace.slack.com/archives/C03L8340TBJ/p1684323096494309
    - https://gitlab.dev.metapixai.com/metapix-cloud/engine/http-api/notification-manager/-/issues/52#note_78792
    '''
    ids = widget.ids

    with allure.step('Check there are duplicates'):
        if len(ids) != len(set(ids)):
            dups = [f'{obj_id}: {count} times' for obj_id, count in Counter(ids).most_common() if count > 1]
            raise LiveFeedDuplicateObjects(', '.join(dups))
    return ids


class LiveFeedWidget(BaseWidget, GridItemsPage):
    type = consts.WIDGET_LIVE_FEED

    @property
    def objects_count(self):
        count = len(check_uniq_ids(self))
        if count == consts.MAX_LIVE_FEED_RESULTS:
            raise LiveFeedOverflowException(self)
        return count
