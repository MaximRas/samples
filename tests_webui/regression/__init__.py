from __future__ import annotations
from datetime import datetime
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Sequence
from typing import TYPE_CHECKING
import logging
import re
import time

import allure

import consts
from tools import ObjectData
from tools import PreconditionException
from tools import check_images_are_equal
from tools import check_images_are_not_equal
from tools.cameras import get_camera_by_id
from tools.image_sender import ImageSender
from tools.steps import get_hover_tooltip
from tools.time_tools import DATETIME_FORMAT_DEFAULT
from tools.time_tools import add_seconds_to_datetime_format
from tools.time_tools import datetime_to_str
from tools.time_tools import parse_date
from tools.time_tools import parse_datetime
from tools.time_tools import timestamp_to_date
from tools.types import BaseType
from tools.types import DateTimeFormatType
from tools.types import StrDateType
from tools.types import XPathType
from tools.webdriver import find_element

from pages.base_page import BasePage
from pages.base_page import is_element_exist
from pages.button import Button
from pages.dropdown import Select
from pages.dropdown import Select_v0_48_4
from pages.grid_items import GridItemsPage
from pages.input_field import Input_v0_48_4
from pages.input_field import InputPassword
from pages.object_card import CardMainThumbnail
from pages.object_card import ObjectCard
from pages.object_popup_dialog import ObjectThumbnailPopup
from pages.object_thumbnail import ObjectThumbnail
from pages.object_thumbnail import PLACEHOLDER_TIME
from pages.root import RootPage
from pages.search.panel_v2 import BaseSearchPanelV2
from pages.settings.licenses import LicensesPage
from pages.settings.tokens import GatewayTokensPage
from pages.widgets import LiveFeedNotShared
from pages.widgets import ValueNotShared

if TYPE_CHECKING:
    from pages.navigation import BaseContentTable
    from pages.widgets import NotSharedWidget

log = logging.getLogger(__name__)


def check_zoom(container: GridItemsPage, check_state_persistence: bool):
    # TODO: does the subj work in headless mode?
    # TODO: check scale
    # TODO: check zoom in
    def _get_state(container: GridItemsPage) -> bytes:
        if isinstance(container, LiveFeedNotShared):
            # Check out size of UICardsContainer: from top of the widget to buttom of the SCREEN
            # So we have to use parent of UICardsContainer: it fits widget
            cards = find_element(container._cards_container, XPathType("./.."))
        else:
            cards = container._cards_container
        return cards.screenshot_as_png

    grid_state_default = _get_state(container)

    with allure.step('Zoom out works'):
        scale_value_zoomed_out = container.zoom_out(times=2)
        grid_state_zoomed_out = _get_state(container)
        check_images_are_not_equal(grid_state_default, grid_state_zoomed_out)

    if check_state_persistence:
        with allure.step('Zoom keeps state after refresh'):
            container.refresh()
            assert scale_value_zoomed_out == container.scale_value
            check_images_are_equal(grid_state_zoomed_out, _get_state(container))

    with allure.step('Reseting zoom works'):
        scale_value_default = container.reset_zoom()
        check_images_are_equal(grid_state_default, _get_state(container))
        assert scale_value_default > scale_value_zoomed_out

    if check_state_persistence:
        with allure.step('Reseting zoom keeps state after refresh'):
            container.refresh()
            assert scale_value_default == container.scale_value
            check_images_are_equal(_get_state(container), grid_state_default)


def check_hide_show_panel(
        panel: BasePage,
        hide_func: Callable,
        show_func: Callable,
        refresh_func: Callable,
) -> None:
    '''
    FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1393
    '''
    time.sleep(2)  # hiding mightn't work if you try to do right after left panel had appeared
    with allure.step('Check hiding'):
        hide_func()
        assert is_element_exist(lambda: panel) is False
        refresh_func()
        assert is_element_exist(lambda: panel) is False

    with allure.step('Check showing'):
        show_func()
        assert is_element_exist(lambda: panel) is True
        refresh_func()
        assert is_element_exist(lambda: panel) is True


def check_show_password_ico(control: InputPassword):
    with allure.step(f'Check "show/hide password" ico for {control}'):
        control.type_text('String!2', clear_with_keyboard=True)
        assert control.type_of_field == 'password'
        control.show()
        assert control.type_of_field == 'text'
        assert control.value == 'String!2'

        control.hide()
        assert control.type_of_field == 'password'

        # teardown
        control.clear_with_keyboard()


def check_submit_button_active_if_all_fields_filled(submit_button: Button, data: Iterable[tuple[Input_v0_48_4, Any]]):
    # TODO: support wrong value
    with allure.step('Check submit button is active only in case all required filed are filled'):
        for control, value in data:
            assert submit_button.is_active() is False
            if isinstance(control, (Select, Select_v0_48_4)):
                control.select_option(value)
            else:
                control.type_text(value)
        assert submit_button.is_active() is True


def get_input_labels(page: BasePage) -> Sequence[str]:
    elements = page.get_objects(XPathType(page.x_root + "//label"))         # legacy input
    elements += page.get_objects(XPathType(page.x_root + "//legend/span"))  # 0.48.4 input
    if not elements:
        raise RuntimeError(f'No input labels found for {page}')
    return tuple(element.text for element in elements)


def get_button_labels(page: BasePage) -> Sequence[str]:
    elements = page.get_objects(XPathType(page.x_root + "//button"))
    if not elements:
        raise RuntimeError(f'No buttons found for {page}')
    labels = tuple(element.text for element in elements)
    return tuple(filter(lambda x: x != '', labels))


def check_pagination(
        page: BaseContentTable,
        fields: Iterable[str],
        pgsize: int = 10) -> None:
    def get_fields(entry):
        result = ""
        if isinstance(fields, (tuple, list)):
            for field in fields:
                result += f'{entry[field]} '
        else:
            result += f'{entry} '

        return result.strip()

    first_page_schema = page.schema
    total_amount = page.pages.total_amount
    if total_amount <= 10:
        raise PreconditionException(f'Not enough entities to check pagination: {total_amount=}')

    # TODO: check the last page
    # TODO: check switching to another pgsize

    with allure.step('Check the first page is OK'):
        assert page.pages.value == "10"   # check default value
        assert len(first_page_schema) == pgsize
        assert page.pages.first_ix == 1
        assert page.pages.last_ix == pgsize
        assert page.pages.button_prev.is_active() is False

    with allure.step('Check the second page is OK and there are no intersections with the first page'):
        page.pages.get_next()
        assert page.pages.first_ix == pgsize + 1
        assert page.pages.total_amount == total_amount
        first_and_second_page_intersection = {get_fields(u) for u in first_page_schema}. \
            intersection({get_fields(u) for u in page.schema})
        assert first_and_second_page_intersection == set()


def check_card_meta(
        actual_meta: Sequence[str],
        expected_meta: Sequence[str],
        base: BaseType) -> None:
    expected_meta = expected_meta[base]

    assert len(expected_meta) == len(actual_meta), \
        f"Expected meta objects {len(expected_meta)} != actual meta objects {len(actual_meta)}"
    for i, expected_line in enumerate(expected_meta):
        if expected_line == PLACEHOLDER_TIME:  # check only format
            parse_datetime(
                actual_meta[i],
                add_seconds_to_datetime_format(DATETIME_FORMAT_DEFAULT),
            )
        else:
            assert re.compile(expected_line).match(actual_meta[i]), \
                f'meta mismatch, got "{actual_meta[i]}", expecting "{expected_line}"'


def parse_widget_updated_date(
        widget: NotSharedWidget,
        datetime_fmt: DateTimeFormatType = DATETIME_FORMAT_DEFAULT,
) -> datetime:
    if widget.type == consts.WIDGET_VALUE:
        autorefresh_button = widget.label_autorefresh_info
    else:
        autorefresh_button = widget.button_autorefresh

    tooltip_text = get_hover_tooltip(widget, autorefresh_button.root)
    date_text = re.findall(r'UPDATED: (.*)', tooltip_text)[0]
    date = parse_datetime(
        text=date_text,
        fmt=add_seconds_to_datetime_format(datetime_fmt),
    )
    log.info(f'Converted "{tooltip_text}" -> {date}')
    return date


def check_autorefresh_delta(widget: NotSharedWidget, sender: ImageSender) -> None:
    date_start = parse_widget_updated_date(widget)
    sender.wait_autorefresh_time()
    date_end = parse_widget_updated_date(widget)
    delta_s = (date_end - date_start).total_seconds()
    assert consts.AUTOREFRESH_TIME <= delta_s < consts.AUTOREFRESH_TIME*2, \
        f'Suspicious autorefresh time: {delta_s} seconds'


def check_datetime_format(
        metapix: RootPage,
        datetime_fmt: DateTimeFormatType) -> None:
    def get_detection_time_hover_tooltip(
            page: ObjectThumbnail | ObjectThumbnailPopup,
            **hover_func_kwargs,
    ) -> StrDateType:
        text = get_hover_tooltip(
            metapix,
            page.meta_elements[-1],
            **hover_func_kwargs,
        ).split('\n')
        assert text[0] == 'OBJECT DETECTION TIME'
        assert len(text) == 2
        return StrDateType(text[1])

    # FYI:
    # - https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1467
    # - https://metapix-workspace.slack.com/archives/C03KBMWC146/p1729605900764919
    datetime_plus_seconds_fmt = add_seconds_to_datetime_format(datetime_fmt)

    log.info('Check object thumbnail from search')
    thumbnail: ObjectThumbnail = yield
    parse_datetime(thumbnail.detection_time, datetime_plus_seconds_fmt)
    parse_datetime(get_detection_time_hover_tooltip(thumbnail), datetime_plus_seconds_fmt)

    log.info('Check object thumbnail popup from search')
    popup: ObjectThumbnailPopup = yield
    parse_datetime(popup.detection_time, datetime_plus_seconds_fmt)
    parse_datetime(get_detection_time_hover_tooltip(popup), datetime_plus_seconds_fmt)

    log.info('Check search panel date filters')
    search_panel: BaseSearchPanelV2 = yield
    parse_datetime(search_panel.date_from.value, datetime_fmt)

    log.info('Check Object card main thumbnail')
    card: ObjectCard = yield
    parse_datetime(card.thumbnail.detection_time, datetime_plus_seconds_fmt)
    parse_datetime(
        get_detection_time_hover_tooltip(
            card.thumbnail, xoffset=5, yoffset=0),
        datetime_plus_seconds_fmt,
    )

    log.info('Check Object card similar object thumbnail')
    similar_object_thumbnail: ObjectThumbnail = yield
    parse_datetime(similar_object_thumbnail.detection_time, datetime_plus_seconds_fmt)
    parse_datetime(get_detection_time_hover_tooltip(similar_object_thumbnail), datetime_plus_seconds_fmt)

    for description in ('widget', 'widget from shared layout', 'shared widget'):
        log.info(f'Check value {description} update time')
        value_widget: ValueNotShared = yield
        parse_widget_updated_date(value_widget, datetime_fmt)

        log.info(f'Check live feed {description} time')
        live_feed_widget: LiveFeedNotShared = yield
        parse_widget_updated_date(live_feed_widget, datetime_fmt)

        log.info(f'Check live feed {description} object thumbnail')
        thumb_from_live_feed: ObjectThumbnail = yield
        parse_datetime(thumb_from_live_feed.detection_time, datetime_plus_seconds_fmt)
        parse_datetime(get_detection_time_hover_tooltip(thumb_from_live_feed), datetime_plus_seconds_fmt)

        log.info(f'Check bar chart {description} tooltip')
        bar_chart_widget = yield
        bar_tooltip = bar_chart_widget.bars[0]._rects[0].tooltip
        bar_date = re.findall('From: (.*)', bar_tooltip[0])[0]
        parse_datetime(bar_date, datetime_fmt)

    log.info('Check Settings -> Licenses table')
    licenses_table: LicensesPage = yield
    parse_date(licenses_table.licenses[0].expires_at, datetime_fmt)
    parse_date(licenses_table.licenses[0].activated_at, datetime_fmt)

    log.info('Check Settings -> Tokens table')
    tokens_table: GatewayTokensPage = yield
    parse_date(tokens_table.tokens[0].generated_at, datetime_fmt)


def check_thumbnail_meta_tooltips(
        thumb: CardMainThumbnail | ObjectThumbnail,
        base: BaseType,
        obj: ObjectData) -> None:
    expected_data = [
        f'OBJECT IDENTIFICATION NUMBER\n{obj.id}',
    ]
    if base == 'face':
        expected_data.append(
            f'FACE INFORMATION\n{obj.meta["gender"].upper()} {obj.meta["age"]}')
    if base == 'vehicle':
        expected_data.extend([
            'LICENSE PLATE\nN/A',
            f'VEHICLE INFORMATION\n{obj.meta["type"].upper()}',
        ])
    expected_data.extend([
            f'DETECTED CAMERA\n{get_camera_by_id(thumb.driver.client, obj.camera_id).name.upper()}',
            f'OBJECT DETECTION TIME\n{datetime_to_str(timestamp_to_date(obj.timestamp), include_seconds=True)}',
    ])
    for ix, meta_element in enumerate(thumb.meta_elements):
        expected_tooltip = expected_data[ix]
        with allure.step(f' - Check tooltip: "{expected_tooltip}"'):
            log.info(f' - Check tooltip: "{expected_tooltip}"')
            actual_tooltip = get_hover_tooltip(thumb, meta_element)
            assert actual_tooltip == expected_tooltip
