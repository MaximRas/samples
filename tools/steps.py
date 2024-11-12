from __future__ import annotations
from concurrent import futures
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Sequence
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING
import logging
import random
import re
import tempfile
import time

from PIL import Image
import allure
import imagehash
import pytest
import requests
from selenium.common.exceptions import ElementNotInteractableException

import consts
from tools.getlist import GetList
from tools import ObjectData
from tools import PreconditionException
from tools import parse_object_type
from tools.cameras import create_camera
from tools.cameras import enable_camera
from tools.cameras import get_camera_by_name
from tools.cameras import get_cameras
from tools.cameras import unarchive_camera
from tools.client import ApiClient
from tools.image_sender import ClusterizationException
from tools.image_sender import ImageSender
from tools.layouts import add_widget_to_layout
from tools.layouts import get_layouts
from tools.locations import bind_camera_to_location
from tools.locations import create_location
from tools.objects import change_object_notes
from tools.objects import get_head_objects
from tools.retry import retry
from tools.search import search_api_v2
from tools.time_tools import Ago
from tools.time_tools import filter_objects_by_timeslice
from tools.time_tools import timestamp_to_date
from tools.types import BaseType
from tools.types import WidgetType
from tools.types import ImageTemplateType
from tools.types import LicPlateType
from tools.types import TimesliceType
from tools.types import IdIntType

from pages.base_page import NoElementException
from pages.button import Button
from pages.camera_picker_legacy import CameraPickerLegacy
from pages.input_field import Input_v0_48_4
if TYPE_CHECKING:
    from tools.cameras import CameraData
    from tools.webdriver import WebElement
    from pages.base_page import BasePage
    from pages.dashboard import DashboardPage
    from pages.navigation import BaseContentTable
    from pages.object_thumbnail import ObjectThumbnail
    from pages.search.results_v2 import SearchResultPageV2
    from pages.widgets import NotSharedChart
    from pages.widgets import NotSharedWidget

log = logging.getLogger(__name__)
InputValidatoinCaseType = Iterable[str] | str


class ClusterizationRetryException(Exception):
    pass


def _filter_objects_belongs_to_cluster(
        parent_id: IdIntType,
        objects: Iterable[ObjectData]) -> Sequence[ObjectData]:
    suitable_objects = []
    for obj in objects:
        if obj.parent_id == parent_id or obj.id == parent_id:
            suitable_objects.append(obj)
    return suitable_objects


def make_vehicle_cluster(
        sender: ImageSender,
        object_type: ImageTemplateType,
        min_cluster_size: int = 2,
        timeslice: Optional[TimesliceType] = consts.DEFAULT_TIMESLICE,
        license_plate: LicPlateType = LicPlateType('12345'),
        # check_is_uniq: bool = False,
        # wait_for_cluster: bool = True,
):
    sender.check_min_objects_count(
        {object_type: min_cluster_size},
        timeslice=timeslice,
        meta={consts.META_LIC_PLATE: license_plate},
    )
    objects = search_api_v2(
        sender.client,
        object_type,
        filters={consts.API_LIC_PLATE: license_plate},
    )
    log.info(f'make_vehicle_cluster: found {len(objects)} objects with license plate: "{license_plate}"')
    if timeslice:
        objects = filter_objects_by_timeslice(
            objects,
            lambda x: timestamp_to_date(x.timestamp),
            timeslice,
        )
        log.info(f'make_vehicle_cluster: found {len(objects)} objects within {timeslice}')
    if not objects:
        raise RuntimeError(f'No {object_type} objects with license plate "{license_plate}" within {timeslice}')
    return objects[0]


@retry(ClusterizationRetryException)
def make_cluster_api(
        sender: ImageSender,
        object_type: ImageTemplateType,
        wait_for_cluster: bool = True,
        min_cluster_size: int = 2,
        check_is_uniq: bool = False,
        timeslice: Optional[TimesliceType] = consts.DEFAULT_TIMESLICE,
):
    def _download_object_image(obj: ObjectData) -> Path:
        res = requests.get(obj.image_url)
        res.raise_for_status()
        output_file = tempfile.mktemp(suffix='.jpg')
        with open(output_file, 'wb') as f_out:
            log.debug(f'{obj.id} -> {output_file}')
            f_out.write(res.content)
        return Path(output_file)

    with allure.step(f'Make cluster for {object_type}'):
        log.info(f'Make cluster for {object_type} {min_cluster_size=}')
        items = get_head_objects(sender.client, object_type)
        if not items:
            log.warning(f'No head object has been found for template: {object_type} (send {min_cluster_size} objects)')
            sender.send(object_type, count=min_cluster_size, wait_for_cluster=wait_for_cluster)
            items = get_head_objects(sender.client, object_type)
            if not items:
                raise ClusterizationException(f'No head object has been found for template: {object_type}')
        if check_is_uniq and len(items) > 1:
            raise PreconditionException(
                f'There is an intersection for template {object_type}: '
                f'found {len(items)} reference objects')

        template_path = sender.get_template_path(object_type)
        hash_template = imagehash.average_hash(Image.open(template_path))
        log.info(f'Check {template_path} against {len(items)} objects')
        for cluster_head in items:
            # look for cluster head which mathes `object_type`
            object_image_path = _download_object_image(cluster_head)
            hash_image = imagehash.average_hash(Image.open(str(object_image_path)))
            object_image_path.unlink()
            is_match = (hash_image - hash_template) <= 3
            if not is_match:
                log.info(f'{template_path} does not match {cluster_head}. distance: {hash_image - hash_template}')
                continue
            log.info(f'Found suitable object: {cluster_head}')

            # calc cluster size
            if timeslice:
                cluster_size = len(
                    _filter_objects_belongs_to_cluster(
                        cluster_head.id,
                        filter_objects_by_timeslice(
                            search_api_v2(sender.client, object_type, recursive=True),
                            lambda x: timestamp_to_date(x.timestamp),
                            timeslice)))
                if cluster_head.cluster_size != cluster_size:
                    log.warning(f'{cluster_head}: patch cluster size (timeslice: {timeslice}) -> {cluster_size}')
                    cluster_head.cluster_size = cluster_size
            else:
                cluster_size = cluster_head.cluster_size

            # send missing files
            if cluster_size < min_cluster_size:
                required_count = min_cluster_size - cluster_size
                log.info(f'More objects required to make cluster: {required_count} of {object_type}')
                sender.send(object_type, count=required_count, wait_for_cluster=wait_for_cluster)
                log.warning(f'{cluster_head}: patch cluster size (missing) -> {cluster_size}+{required_count}')
                cluster_head.cluster_size += required_count
            return cluster_head
        sender.send(object_type, count=min_cluster_size, wait_for_cluster=wait_for_cluster)
        raise ClusterizationRetryException


def find_clusters_api(
        client: ApiClient,
        base: ImageTemplateType,
        count: int = 1,
        **kwargs,
) -> list[ObjectData]:
    min_cluster_size = kwargs.pop('min_cluster_size', 2)
    max_cluster_size = kwargs.pop('max_cluster_size', 25)
    values_to_avoid = kwargs.pop('values_to_avoid', [])

    suitable_clusters = []

    with allure.step(f'Looking for {base} object with cluster'):
        log.info(f'Looking for {base} object with cluster {min_cluster_size=} {max_cluster_size=}')
        for item in get_head_objects(client, base):
            cluster_size = item.cluster_size
            if cluster_size in values_to_avoid:
                log.warning(f'{item} has wrong cluster size: {values_to_avoid}')
                continue
            if not cluster_size:
                continue
            if cluster_size < min_cluster_size:
                log.debug(f'{item} too small cluster')
                continue
            if cluster_size > max_cluster_size:
                log.debug(f'{item} too big cluster')
                continue
            log.info(f'Found suitable item: {item}')
            suitable_clusters.append(item)
            if len(suitable_clusters) == count:
                break
        if len(suitable_clusters) != count:
            raise RuntimeError('Not enough suitable clusters')
        return GetList(suitable_clusters)


def prepare_objects_with_notes(
        sender: ImageSender,
        base: ImageTemplateType,
        notes_count: int) -> None:
    with allure.step(f'Prepare test: make {notes_count} noted objects'):
        sender.check_min_objects_count({base: notes_count}, timeslice=None)

        items = search_api_v2(sender.client, base)
        random.shuffle(list(items))
        for ix, item in enumerate(items[:notes_count]):
            change_object_notes(sender.client, item, f'notes #{ix}')


def find_card_with_eye(search_results: SearchResultPageV2) -> ObjectThumbnail:
    for card in search_results.thumbs:
        if card.has_eye():
            return card
    raise RuntimeError(f'{search_results}: No card with eye has been found')


def find_card_without_eye(search_results: SearchResultPageV2) -> ObjectThumbnail:
    '''
    This function expect that search works and cluster size (eye icon) is correct
    Bugs may lead to unexpected results.
    For example the problem with cluster size of non-reference objects:
      https://metapix-workspace.slack.com/archives/C03KJ7TM411/p1685112922250979
    '''
    with allure.step('Looking for card without cluster'):
        log.info('Looking for card without cluster')
        for card in search_results.thumbs:
            if not card.has_eye():
                log.info(f'Found card without cluster: {card}')
                return card
        raise RuntimeError('No card without cluster')


def create_location_schema_api(
        client: ApiClient,
        schema: dict | list,
) -> None:
    def _remove_plus_or_minus(loc_name):
        return re.sub(r'^[▲▼]?\s?(.+)', r'\1', loc_name)

    def apply_schema_to_location(client: ApiClient, parent_loc, schema):
        if isinstance(schema, list):
            for entity_name in schema:
                if isinstance(entity_name, dict):
                    apply_schema_to_location(client, parent_loc, entity_name)
                elif isinstance(entity_name, str):
                    bind_camera_to_location(client, get_camera_by_name(client, entity_name), parent_loc)
                elif isinstance(entity_name, (list, tuple)):
                    apply_schema_to_location(client, parent_loc, entity_name)
                else:
                    raise ValueError(f"Unknown node: {entity_name}")
        elif isinstance(schema, dict):
            for nested_loc_name in schema:
                nested_loc = create_location(
                    client,
                    _remove_plus_or_minus(nested_loc_name),
                    parent_location_id=parent_loc.id,
                )
                apply_schema_to_location(client, nested_loc, schema[nested_loc_name])
        else:
            raise RuntimeError('Unexpected behavior')
    for root_loc_name in schema:
        apply_schema_to_location(
            client,
            create_location(client, _remove_plus_or_minus(root_loc_name)),
            schema[root_loc_name],
        )


def check_filtering_with_empty_location(
        filter_dialog: CameraPickerLegacy,
        loc_name: str) -> None:
    from pages.base_page import ElementIsNotClickableException

    filter_dialog.set_filters(locations=[loc_name])
    with allure.step('It is not possible to search with empty location'):
        with pytest.raises(ElementIsNotClickableException):
            filter_dialog.apply()
        assert filter_dialog.label_selected_text == 'Error\nYou must allocate at least one camera'


def check_input_validation(
        control: Input_v0_48_4,
        valid: Iterable[InputValidatoinCaseType],
        invalid: Iterable[InputValidatoinCaseType],
        button: Optional[Button] = None) -> None:
    with allure.step(f'Check validation: {control}'):
        log.info(f'Check validation: {control}')

        def _check(
                cases: Iterable[InputValidatoinCaseType],
                expected_tooltip_state: bool,
                expected_button_state: bool,
                error_message: str) -> None:
            for text in cases:
                if isinstance(text, tuple):
                    assert expected_tooltip_state is True
                    text, expected_tooltip = text
                else:
                    expected_tooltip = None
                text = str(text)  # fix error: Argument of type "str | Iterable[str]" cannot be assigned to parameter "text" of type "str" in function "type_text"

                with allure.step(f'Check case: "{text}"'):
                    with allure.step(f'Check tooltip for {control}'):
                        control.type_text(text, clear_with_keyboard=True)
                        if expected_tooltip:
                            assert control.tooltip == expected_tooltip, f'Expected: "{expected_tooltip}"'
                        else:
                            assert bool(control.tooltip) is expected_tooltip_state

                    if button:
                        with allure.step(f'Check {button} is {"active" if expected_button_state else "inactive"}'):
                            log.info(f'Check {button} is {"active" if expected_button_state else "inactive"}')
                            assert button.is_active() is expected_button_state

        with allure.step('Check valid cases'):
            _check(valid, False, True, "warning appeared")
        with allure.step('Check invalid cases'):
            _check(invalid, True, False, "warning didn't appear")

        # teardown
        control.clear_with_keyboard()


def check_company_name_validation(control: Input_v0_48_4):
    ''' is used in two cases: 1) license server and 2) user settings'''
    # TODO: add more cases
    check_input_validation(
        control,
        [
            'S78',  # https://gitlab.dev.metapixai.com/metapix-cloud/license-server/web-app/-/issues/11
        ],
        [
        ],
    )


def check_name_validation(
        control: Input_v0_48_4,
        button: Optional[Button] = None) -> None:
    # TODO: add too short and too long
    # TODO: check tooltip text
    check_input_validation(
        control=control,
        valid=[
            'John',
            'Master Kenobi',  # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/925
            'Olivia-Faye',    # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/925
        ],
        invalid=[
            'First_name!',
            'FirstName123',
            'FirstName123!@#',
            '      ',         # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1084
            '',
        ],
        button=button,
    )


def check_email_validation(control: Input_v0_48_4, allow_empty: bool = False):
    valid_emails = ['autotest@metapix.ai']
    invalid_emails = ['email']
    if not allow_empty:
        invalid_emails.append('')
    check_input_validation(control, valid_emails, invalid_emails)


def check_input_is_disabled(control: Input_v0_48_4) -> None:
    with allure.step(f'Check control is disabled: {control}'):
        log.info(f'Check control is disabled: {control}')
        with pytest.raises(ElementNotInteractableException):
            control.clear_with_keyboard()


def check_password_validation(
        control: Input_v0_48_4,
        button: Optional[Button] = None) -> None:
    ''' FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1384 '''
    check_input_validation(
        control,
        ['String!2'],
        [
            ('', 'Field cannot be empty'),
            ('123456789', 'The field must include at least one number, one uppercase letter, one lowercase letter, and one of the following special characters: !, @, #, $, %, ^, &, *'),
        ],
        button=button,
    )


def _choose_widget_type(available_types: Iterable[str]) -> str:
    available_types = list(available_types)
    # if consts.WIDGET_LIVE_FEED in available_types:
    #     available_types.remove(consts.WIDGET_LIVE_FEED)   # have problems with double requests and autorefresh for shared widget
    # available_types.remove(consts.WIDGET_VALUE)  # https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1491
    if not available_types:
        raise RuntimeError
    return random.choice(available_types)


def create_any_chart(
        dashboard: DashboardPage,
        base: Optional[ImageTemplateType] = None) -> NotSharedChart:
    widget_type = _choose_widget_type(consts.WIDGET_ALL_CHARTS)
    available_bases = ['face', 'vehicle', 'person']
    if widget_type == consts.WIDGET_PIE_CHART:
        available_bases.remove('person')

    return create_widget_api(  # type: ignore[reportReturnType]
        dashboard=dashboard,
        widget_type=widget_type,
        template=base or random.choice(available_bases),
        title=None,
    )


def create_any_widget(
        dashboard: DashboardPage,
        base: Optional[BaseType] = None,
        title: Optional[str] = None) -> NotSharedWidget:
    # TODO: do not create live feed if there are too much objects
    widget_type = _choose_widget_type(consts.WIDGET_ALL_TYPES)
    available_bases = ['face', 'vehicle', 'person']
    if widget_type == consts.WIDGET_PIE_CHART:
        available_bases.remove('person')

    return create_widget_api(
        dashboard=dashboard,
        widget_type=widget_type,
        template=base or random.choice(available_bases),  # type: ignore
        title=title,
    )


@retry(NoElementException)
def get_hover_tooltip(
        metapix: BasePage,
        element: WebElement,
        xoffset: Optional[int] = None,
        yoffset: Optional[int] = None) -> str:
    chain = metapix._action_chains
    if xoffset is not None and yoffset is not None:
        chain = chain.move_to_element_with_offset(element, xoffset=xoffset, yoffset=yoffset)
    else:
        chain = chain.move_to_element(element)
    chain.perform()
    time.sleep(0.5)  # wait tooltip rendered
    return metapix.hover_tooltip


def create_widget_api(
        dashboard: DashboardPage,
        widget_type: WidgetType,
        template: ImageTemplateType,
        title: Optional[str] = None,
) -> NotSharedWidget:
    base = parse_object_type(template)[0]
    if widget_type == consts.WIDGET_PIE_CHART and base == 'person':
        raise RuntimeError('Pie chart does not support persons')
    if base not in ('person', 'vehicle', 'face'):
        raise RuntimeError(f'Unknown base type: {base}')
    client = dashboard.driver.client
    title = title or f'{base.capitalize()} {widget_type}'
    log.info(f'Create {widget_type} {base=} title="{title}"')
    # filters
    filters = [
        f'object_type:{base}',
        'image_quality:good',
    ]
    if base == 'vehicle':
        filters.append('vehicle_type:all')
    if base == 'face':
        filters.append('person_gender:all')
        filters.append('person_age:1-99')

    # payload
    payload = {
        'size': [1, 1],
        'type': widget_type if widget_type != consts.WIDGET_BAR_CHART else 'hist_chart',
        'name': title,
        'filters': filters,
    }
    if widget_type == consts.WIDGET_LIVE_FEED:
        payload['online'] = True
        payload['type'] = f'{base}_feed'
    if widget_type in consts.WIDGET_ALL_CHARTS:
        payload['state'] = {
            'legend': [],
        }

    with allure.step(f'Create {widget_type} {base=} title="{title}"'):
        # perform request
        response = client.request(
            'post',
            f'/{consts.SERVICE_LAYOUT_MANAGER}/widgets',
            data=payload,
            expected_code=201,
        ).json()
        widget_id = response['id']
        log.info(f' - created widget id: {widget_id}')

        layout = [layout for layout in get_layouts(client) if layout.default is True][0]
        add_widget_to_layout(client, widget_id, layout)

        dashboard.refresh()
        return dashboard.get_widget(title=title, widget_type=widget_type)


def prepare_cameras_for_suite(
        client: ApiClient,
        count: int, *args, **kwargs) -> Iterable[CameraData]:
    def create_and_activate(
            client: ApiClient,
            name: str,
            existing_cameras: Iterable[CameraData]):
        try:
            camera = next(filter(lambda x: x.name == name, existing_cameras))
        except StopIteration:
            log.warning(f'Create camera {name}')
            camera = create_camera(client, name)
            enable_camera(client, camera)
        else:
            if not camera.active:
                log.warning(f'Camera {name} exists but is not enabled')
                enable_camera(client, camera)
            if camera.archived:
                log.warning(f'Camera {name} exists but archived')
                unarchive_camera(client, camera)

    with allure.step(f'Prepare {count} cameras for client {client}'):
        log.info(f'Prepare {count} cameras for client {client}')
        existing_cameras = get_cameras(client)
        with futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures_ = []
            for ix in range(count):
                futures_.append(
                    executor.submit(
                        create_and_activate,
                        client=client,
                        name=f'camera-{ix+1}',
                        existing_cameras=existing_cameras,
                    )
                )
            futures.wait(futures_)
            for future in futures_:
                if future.exception():
                    raise future.exception()
        time.sleep(3)
        return get_cameras(client)


def fill_intervals_with_objects(
        sender: ImageSender,
        object_type: ImageTemplateType,
        timeslice: TimesliceType | Ago,
        detalization: int | str) -> None:
    # TODO: fix type hind for `object type` and `timeslice`
    if isinstance(timeslice, str):
        timeslice_sec = consts.TIMESLICES_IN_SECONDS[timeslice]
    elif isinstance(timeslice, Ago):
        timeslice_sec = abs(timeslice.delta)
    else:
        raise RuntimeError(f'Unknown timeslice type: {type(timeslice)}')

    if isinstance(detalization, str):
        detalization_sec = consts.DETS_IN_SECONDS[detalization]
    elif isinstance(detalization, int):
        detalization_sec = detalization
    else:
        raise RuntimeError(f'Unknown detalization type: {type(detalization)}')

    for ix in range(timeslice_sec // detalization_sec):
        delta_to = Ago(-ix * detalization_sec)
        delta_from = Ago(-1 * (ix + 1) * detalization_sec)
        log.info(f'Interval #{ix}: {delta_from} ... {delta_to}')
        sender.objects_count_in_interval(object_type, delta_from, delta_to, min_objects_count=1)


def find_in_all_pages(page: BaseContentTable, entity: Mapping[str, Any]) -> Mapping[str, Any]:
    from pages.pagination import PaginationException

    with allure.step(f'{page}: try to find: {entity}'):
        log.info(f'{page}: try to find: {entity}')
        if page.pages.total_amount > 500:
            raise RuntimeError(f'Too much companies: {page.pages.total_amount}')
        page.pages.set_value(consts.PAGINATION_MAX)
        while True:
            if entity in page.schema:
                return entity
            try:
                page.pages.get_next()
            except PaginationException as exc:
                raise RuntimeError(f'Not found: {entity}') from exc
