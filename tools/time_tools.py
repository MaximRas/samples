import logging
import re
import time
from datetime import datetime
from datetime import timedelta
from typing import NewType
from typing import Optional
from typing import Callable
from typing import Sequence

import allure
from typing_extensions import Self

import consts
from tools import ResponseJson
from tools import ObjectData
from tools.client import ApiClient
from tools.users import get_active_user
from tools.types import StrDateType
from tools.types import DateTimeFormatType

DATETIME_FORMAT_MDY_SLASH_12H = DateTimeFormatType('%m/%d/%Y %I:%M %p')
DATETIME_FORMAT_DMY_DASH_24H = DateTimeFormatType('%d-%m-%Y %H:%M')
DATETIME_FORMAT_DMY_DASH_12H = DateTimeFormatType('%d-%m-%Y %I:%M %p')
DATETIME_FORMAT_DEFAULT = DATETIME_FORMAT_MDY_SLASH_12H
log = logging.getLogger('tools.time')
TimeZone = NewType('TimeZone', str)


def remove_time_from_datetime_format(date_time_format: DateTimeFormatType) -> DateTimeFormatType:
    ''' Get date regex from datetime regex '''
    parts = date_time_format.split()
    return DateTimeFormatType(parts[0])


def _parse_time_delta(str_delta: str) -> int:
    '''
    Used by `Ago` class
    converts strings like into integers:
    "-1h" ->  -3600
    '''
    delta = 0
    has_leading_minus = str_delta[0] == '-'
    for part in re.findall(r'\d+\w{1}', str_delta.removeprefix('-')):
        number, last_char = part[:-1], part[-1]
        assert number.isnumeric()
        assert last_char.isalpha()
        number = int(number)
        if last_char == 'h':
            delta += number * consts.HOUR_SECONDS
        elif last_char == 'm':
            delta += number * 60
        elif last_char == 's':
            delta += number
        elif last_char == 'd':
            delta += number * consts.DAY_SECONDS
        elif last_char == 'w':
            delta += number * 7*consts.DAY_SECONDS
        else:
            raise RuntimeError(f'Unkonwn char "{last_char}" in time delta string: {str_delta}')
    if has_leading_minus:
        delta *= -1
    log.debug(f'Time delta converted: "{str_delta}" -> {delta}')
    return delta


def _ceil_timestampt(timestamp: float) -> int:
    timestamp = int(timestamp)
    minute = timestamp_to_date(timestamp).minute
    minute_diff = 5 - minute % 5
    timestamp += minute_diff * 60
    return timestamp


class Ago:
    ''' timestamp and datetime will be aligned with 5 min '''
    def __init__(self, delta: int | str):
        if isinstance(delta, str):
            delta = _parse_time_delta(delta)
        assert delta <= 0
        time_now = _ceil_timestampt(time.time())
        self.delta = delta
        self.timestamp = time_now + self.delta
        self.dt = timestamp_to_date(self.timestamp)

    def __str__(self):
        return f'Delta {self.delta}s: {format_date_chart_like(self.dt)}'

    def __sub__(self, o) -> Self:
        return self.__class__(o.delta - self.delta)

    def __add__(self, o) -> Self:
        return self.__class__(self.delta + o.delta)

    def __mul__(self, n) -> Self:
        return self.__class__(self.delta*n)

    def __truediv__(self, n) -> Self:
        return self.__class__(self.delta / n)

    def __lt__(self, o) -> Self:
        return self.delta < o.delta


def now_pst() -> datetime:
    """ Current datetime with US/Pacific timezone """
    return datetime.now().astimezone(consts.tz_pst)


def timedelta_hours(delta: timedelta) -> int:
    return int(abs(delta.total_seconds()//consts.HOUR_SECONDS))


def change_timezone(
        client: ApiClient,
        timezone: TimeZone,
) -> ResponseJson:
    with allure.step(f'Change timezone -> {timezone}'):
        log.info(f'Change timezone -> {timezone}')
        user = get_active_user(client)
        response = client.request(
            "patch",
            f'/{consts.SERVICE_AUTH_MANAGER}/users/{user.id}',
            data={"timezone": timezone},
            expected_code=200,
        )
        return response.json()


def timestamp_to_date(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp).astimezone(consts.tz_pst)


def format_date_chart_like(date: datetime) -> StrDateType:
    ''' Date in the same format as chart X-axis '''
    return StrDateType(date.strftime('%d %b %I:%M %p'))


def _round_time(
        date: datetime,
        round_to: int,
) -> datetime:
    """
    This function has been stolen from **object_manager** repo.

    Round a datetime object to any time lapse in seconds
    dt : datetime.datetime object
    round_to : Closest number of seconds to round to
    """
    if not round_to:
        return date
    seconds = (date.replace(tzinfo=None) - date.min).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    new_date = date + timedelta(0, rounding - seconds, -date.microsecond)
    # log.debug(f'Round date {date} -> {new_date} (by {round_to / 60} minutes)')
    return new_date


def filter_objects_by_timestamps(
        objects: Sequence[ObjectData],
        get_time: Callable[[ObjectData], datetime],
        time_from,
        time_to,
) -> Sequence[ObjectData]:
    if time_from:
        objects = tuple(filter(lambda x: get_time(x) >= time_from, objects))
    if time_to:
        objects = tuple(filter(lambda x: get_time(x) <= time_to, objects))
    return objects


def filter_objects_by_timeslice(
        objects: Sequence[ObjectData],
        get_time: Callable[[ObjectData], datetime],
        timeslice: Optional[str],
        detalization=None,
) -> Sequence[ObjectData]:
    # TODO: strict type hint for `timeslice`
    if timeslice is None:
        return objects
    if timeslice == 'custom_default':
        timeslice = '12h'
        detalization = 0
    if detalization is None:
        detalization = consts.TIMESLICE_DETAILS[timeslice][0]  # 1h -> 5 minutes
        if isinstance(detalization, str):
            detalization = consts.DETS_IN_SECONDS[detalization]    # 5 minutes -> 60 * 5
    date_from = now_pst() - timedelta(seconds=consts.TIMESLICES_IN_SECONDS[timeslice])
    date_from = _round_time(date_from, detalization)
    date_to = now_pst()  # ceil_timestampt ???
    return filter_objects_by_timestamps(objects, get_time, date_from, date_to)


def add_seconds_to_datetime_format(fmt: DateTimeFormatType) -> DateTimeFormatType:
    new_regex = fmt.replace('%M', '%M:%S')
    return DateTimeFormatType(new_regex)


def parse_datetime(
        text: StrDateType,
        fmt: DateTimeFormatType = DATETIME_FORMAT_DEFAULT) -> datetime:
    return datetime.strptime(text, fmt)


def parse_date(text: StrDateType, fmt: Optional[DateTimeFormatType] = None) -> datetime:
    if not fmt:
        fmt = DATETIME_FORMAT_DEFAULT
    fmt = remove_time_from_datetime_format(fmt)
    return datetime.strptime(text, fmt).astimezone(consts.tz_pst)


def is_12h_time_format(fmt: DateTimeFormatType) -> bool:
    return '%p' in fmt


def date_to_str(date: datetime, fmt: Optional[DateTimeFormatType] = None) -> StrDateType:
    if not fmt:
        fmt = DATETIME_FORMAT_DEFAULT
    fmt = remove_time_from_datetime_format(fmt)
    date_formatted = date.strftime(fmt)
    # return re.sub(r"\b0(\d)", r"\1", date_formatted)  # remove zero-padding
    return StrDateType(date_formatted)


def datetime_to_str(
        date: datetime,
        fmt: Optional[DateTimeFormatType] = None,
        include_seconds: bool = False) -> StrDateType:
    if not fmt:
        fmt = DATETIME_FORMAT_DEFAULT
    if include_seconds:
        fmt = add_seconds_to_datetime_format(fmt)
    date_formatted = date.strftime(fmt)
    return StrDateType(date_formatted)
