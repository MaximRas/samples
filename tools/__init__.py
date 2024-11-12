from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Generator
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict
import io
import json
import logging
import random
import string
import time

from PIL import Image
from allure_commons.types import AttachmentType
from requests.exceptions import JSONDecodeError
from selenium.common.exceptions import TimeoutException
from urllib3.exceptions import MaxRetryError
from strenum import StrEnum
import allure

from tools import config
from tools.types import ApiCompanyType
from tools.types import ApiUserRole
from tools.types import BaseType
from tools.types import CompanyNameType
from tools.types import EmailType
from tools.types import IdIntType
from tools.types import IdStrType
from tools.types import ImageTemplateType
from tools.types import TimestampType
from tools.types import UrlType
from tools.webdriver import CustomWebDriver
from tools.webdriver import WebElement
if TYPE_CHECKING:
    from tools.image_sender import Roi
    from tools.image_sender import MetaType

log = logging.getLogger('tools')
WAIT_OBJECTS_ARRIVE_TIME = timedelta(seconds=5)
WAIT_CLICKHOUSE_LAG = timedelta(seconds=10)
ResponseException = TypedDict('ResponseException', {'message': str})


class UndefinedElementException(Exception):
    pass


class ResponseJson(TypedDict):
    pass


class PreconditionException(Exception):
    pass


class NoDataFoundException(Exception):
    pass


class RequestStatusCodeException(Exception):
    """ Request status code doesn't match expected value """


@dataclass
class CompanyShortData:
    id: IdIntType
    name: CompanyNameType
    role: ApiUserRole

    def __str__(self):
        return f'Company "{self.name}"'


@dataclass
class CompanyRoleData:
    id: IdIntType
    name: CompanyNameType
    role: ApiUserRole

    def __str__(self):
        return f'Company id={self.id} name="{self.name}" role="{str(self.role)}"'


@dataclass
class CompanyInfoData:
    id: IdIntType
    parent_company_id: IdIntType
    name: CompanyNameType
    company_type: ApiCompanyType
    # email_address
    # contact_address
    # created_by
    # deleted_by
    # rank
    # retention_period

    def __str__(self):
        return f'Company id={self.id} name="{self.name}" type="{str(self.company_type)}"'


@dataclass
class UserData:
    id: IdStrType
    email: EmailType
    first_name: str
    last_name: str
    role: ApiUserRole
    photo_url: UrlType
    timezone: str
    current_password: str

    def __str__(self):
        return f'User email:{self.email}'


@dataclass
class ObjectData:
    id: IdIntType
    cluster_size: int
    base: BaseType
    camera_id: IdStrType
    timestamp: TimestampType
    roi: Roi
    meta: MetaType
    is_reference: bool
    parent_id: Optional[int]
    image_url: UrlType

    def __str__(self):
        return f'Object id={self.id} base={self.base} cluster_size={self.cluster_size}'


def create_enum_from_value(enum: StrEnum, value: str) -> StrEnum:  # TODO: fix typing
    for member in enum:
        if member == value:
            return member
    raise RuntimeError(f'enum does not value value "{value}"')


def create_company_role_data(data: dict) -> CompanyRoleData:
    return CompanyRoleData(
        id=data['id'],
        name=data['name'],
        role=create_enum_from_value(ApiUserRole, data['role']),
    )


def create_company_info_data(data: dict) -> CompanyInfoData:
    return CompanyInfoData(
        id=data['id'],
        parent_company_id=data['parent_company_id'],
        name=data['name'],
        company_type=create_enum_from_value(ApiCompanyType, data['company_type']),
    )


def create_user_data(data: dict) -> UserData:
    return UserData(
        id=data['id'],
        email=EmailType(data['email']),
        first_name=data['first_name'],
        last_name=data['last_name'],
        role=create_enum_from_value(ApiUserRole, data['role']),
        photo_url=data['photo_url'],
        timezone=data['timezone'],
        current_password=config.user_config['_default_pwd'],
    )


def json_to_object(data: dict, camera_id_field: str) -> ObjectData:
    '''
    FYI: why camera_id_field is required?
      object-manager/objects/<object-id> response stores camera id in `camera` field
      object-manager/v2/search/<base> response stores camera id in `camera_id` field
    '''
    return ObjectData(
        id=data['id'],
        cluster_size=data['cluster_size'],
        base=data['type'],
        camera_id=data[camera_id_field],
        timestamp=data['timestamp'],
        roi=data['roi'],
        is_reference=data['is_reference'],
        meta=data['meta'],
        parent_id=data['parent_id'],
        image_url=data['image_url'],
    )


def compare_images_by_hash(
        s1: bytes,
        s2: bytes,
        predicate: Callable,
        description: str = '') -> None:
    import imagehash

    with allure.step(f'Compare images with imagehash: {description}'):
        log.info(f'Compare images with imagehash: {description}')
        hash1 = imagehash.average_hash(Image.open(io.BytesIO(s1)), hash_size=16)
        hash2 = imagehash.average_hash(Image.open(io.BytesIO(s2)), hash_size=16)

        result = predicate(hash1, hash2)
        if not result:
            for ix, image in enumerate((s1, s2)):
                allure.attach(
                    name=f'Image to compare #{ix+1}',
                    body=image,
                    attachment_type=AttachmentType.PNG,
                )
            raise AssertionError('Failed predicate check')


def check_images_are_equal(s1: bytes, s2: bytes) -> None:
    compare_images_by_hash(
        s1, s2,
        lambda h1, h2: h1 - h2 == 0,
        'Check images are equal',
    )


def check_images_are_not_equal(s1: bytes, s2: bytes, thr: int = 1) -> None:
    compare_images_by_hash(
        s1, s2,
        lambda h1, h2: h1 - h2 >= thr,
        'Check images are different',
    )


def parse_object_type(
        object_type: ImageTemplateType,
) -> tuple[BaseType, Optional[str], Optional[str]]:
    """
    Returns base, full attribute and short attribute
    For example: "vehicle-type-sedan" -> ("vehicle", "type-sedan", "sedan")
    """
    base, *attribute = object_type.split("-")
    if len(attribute) == 0:
        # example: object_type = "person"
        return base, None, None
    elif len(attribute) == 1:
        # example: object_type = "face-male"
        return base, attribute[0], attribute[0]
    elif len(attribute) == 2:
        # example: object_type = "vehicle-type-sedan"
        return base, "-".join(attribute), attribute[-1]
    else:
        raise ValueError(f'unexpected object type: {object_type}')


def generate_id_from_time(random_length: int = 5) -> str:
    return ''.join(
        random.choices(string.ascii_uppercase + string.ascii_lowercase, k=random_length)
    )


def wait_objects_arrive(clickhouse_lag: bool = True) -> None:
    from tools.time_tools import now_pst
    # TODO: clickhouse_lag=False by default
    if not config.last_object_sent_time:
        return
    last_object_will_arrive = config.last_object_sent_time + WAIT_OBJECTS_ARRIVE_TIME
    if clickhouse_lag:
        last_object_will_arrive += WAIT_CLICKHOUSE_LAG
    seconds_to_wait = round((last_object_will_arrive - now_pst()).total_seconds(), 2)
    if seconds_to_wait > 0:
        log.info(f"Wait objects arrive: {seconds_to_wait} seconds")
        time.sleep(seconds_to_wait)


def get_xhr_requests(driver: CustomWebDriver) -> Iterable[Mapping]:
    network = json.loads(driver.execute_script("return JSON.stringify(window.performance.getEntries());"))
    return [req for req in network if "initiatorType" in req.keys() and req["initiatorType"] == "xmlhttprequest"]


def run_test(gen: Generator) -> Generator:
    '''
    Init generator and return it
    For the sake of semantic
    '''
    gen.send(None)
    return gen


def send_value_to_test(gen: Generator, *values) -> None:
    try:
        if len(values) == 1:
            gen.send(*values)
        else:
            gen.send(values)   # to be able to get values like that: widget1, widget2 = yield
    except StopIteration:
        pass


def parse_api_exception_message(error_exc) -> ResponseException:
    '''
    Example:
    {"code":400,"status":"error","message":"No more licenses available to activate camera"}
    '''
    try:
        # return json.loads(str(error_exc).replace("'", '"'))
        return json.loads(str(error_exc))
    except JSONDecodeError as exc:
        raise RuntimeError(f'Unable to parse: {error_exc}') from exc


def attribute_to_bool(element: WebElement, attrib: str) -> bool:
    value = element.get_attribute(attrib)
    if value not in ('true', 'false', None):
        raise ValueError(f'Attribute {attrib} wrong value: {value}')
    return value == 'true'


def sort_list_of_dicts(schema: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    key_to_dict = {}
    for item in schema:
        key = list(item.keys())[0]
        key_to_dict[key] = item
    result = []
    for key in sorted(key_to_dict.keys()):
        result.append(key_to_dict[key])
    return result


def sort_list_by_dict_key(schema: Iterable[Mapping[str, Any]], key_to_sort: str) -> Iterable[Mapping[str, Any]]:
    key_to_dict = {}
    for item in schema:
        key_to_dict[item[key_to_sort].lower()] = item
    result = []
    for key in sorted(key_to_dict.keys()):
        result.append(key_to_dict[key])
    return result


def join_url(url: UrlType, path: str) -> UrlType:
    if url.endswith('/') and path.startswith('/'):
        path = path[1:]
    full_url = url + path
    log.debug(f'{url} + {path} == {full_url}')
    return UrlType(full_url)


def merge_lists_in_dict(
        dict_with_lists: dict[str, Any],
        new_key: str,
        *old_keys: Iterable[str]) -> None:
    # TODO: example
    if new_key not in dict_with_lists:
        dict_with_lists[new_key] = []
    for old_key_ in old_keys:
        if old_key_ not in dict_with_lists:
            continue
        dict_with_lists[new_key] += dict_with_lists[old_key_]
        del dict_with_lists[old_key_]
    if not dict_with_lists[new_key]:
        del dict_with_lists[new_key]


def attach_screenshot(driver: CustomWebDriver, screenshot_name: str) -> None:
    try:
        allure.attach(name=screenshot_name,
                      body=driver.get_screenshot_as_png(),
                      attachment_type=AttachmentType.PNG)
    except (TimeoutException, MaxRetryError) as e:
        log.error(f"Exception during saving screenhost: {e}")


def check_enum_has_value(enum: StrEnum, expected_value: str) -> str:
    for member in enum:
        log.debug(f'Check "{member.value}" vs "{expected_value}"')
        if member.lower() == expected_value.lower():
            return expected_value
    raise RuntimeError(f'enum does not have value "{expected_value}"')


def fix_page_path(path: str) -> str:
    return f'/beta{path}' if config.is_beta else path


def are_dicts_equal(d1: Mapping, d2: Mapping) -> bool:
    from dictdiffer import diff

    diffs = tuple(diff(d1, d2))
    if not diffs:
        return True
    for entry in diffs:
        log.warning(entry)
    return False
