import logging
import math
import re
import time
from datetime import datetime
from typing import Callable

import allure
from typing_extensions import Self
from selenium.webdriver.common.keys import Keys

import consts
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.retry import retry
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement
from pages.base_page import BasePage

log = logging.getLogger(__name__)

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


class NoTextException(Exception):
    pass


class YearDialog(BasePage):
    def __init__(
            self,
            x_root: XPathType = XPathType(""),
            *args, **kwargs):
        self.x_root = XPathType(x_root + "//div[@class='MuiPickersYearSelection-container']")
        super().__init__(*args, **kwargs)

    def _get_year_element(self, year) -> WebElement:
        year_elem = self.get_object(
            XPathType(self.x_root + f"//div[text()='{year}']"),
            is_clickable=True,
        )
        self.scroll_to_element(year_elem)
        return year_elem

    def select_year(self, year) -> None:
        with allure.step(f'Select year: {year}'):
            log.info(f'Select year: {year}')
            self._get_year_element(year).click()


class CalendarPage(BasePage):
    """ Calendar widget """
    def __init__(
            self,
            x_root: XPathType = XPathType(""),
            *args, **kwargs):
        self.x_root = XPathType(x_root + "//div[child::div[contains(@class, 'Calendar-transitionContainer')]]")
        super().__init__(*args, **kwargs)

    @property
    def day(self) -> int:
        selected_day = self.get_desc_obj(XPathType('//button[contains(@class, "daySelected")]'))
        return int(selected_day.text)

    @property
    def month_str(self) -> str:
        element = self.get_desc_obj(XPathType("//div[contains(@class, 'MuiPickersCalendarHeader')]/p"))
        log.debug(f'Parse {element.text}')
        month = re.findall(r'(\w+)\s+\d+', element.text)[0]
        return month

    @property
    def month_int(self) -> int:
        return MONTHS.index(self.month_str) + 1

    @property
    def arrow_next(self) -> IcoButton:
        return get_ico_button(self, IcoType('M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z'))

    @property
    def arrow_prev(self) -> IcoButton:
        return get_ico_button(self, IcoType('M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z'))

    def select_day(self, date) -> None:
        with allure.step(f'Select day: {date}'):
            log.info(f'Select day: {date}')
            self.get_object(
                XPathType(self.x_root + f"//button[descendant::p='{date}' and not(contains(@class, 'hidden'))]/.."),
                is_clickable=True,
            ).click()

    def select_month(self, expected_month: int) -> None:
        with allure.step(f'Select month: {expected_month}'):
            log.info(f'Select month: {expected_month}')
            month_diff = self.month_int - expected_month
            button_month = self.arrow_prev if month_diff > 0 else self.arrow_next
            if month_diff != 0:
                for _ in range(abs(month_diff)):
                    button_month.click()
            # FYI: Got UndefinedElementException wihtout delay
            time.sleep(1.5)
            if self.month_int != expected_month:
                raise RuntimeError(f'Wrong month was set: {self.month_int} (expected: {expected_month})')


class ClockPage(BasePage):
    CLOCK_WISE = 1
    COUNTER_CLOCK_WISE = -1
    ONE_MIN_DEGREE = 6

    def __init__(
            self,
            x_root: XPathType = XPathType(""),
            *args, **kwargs):
        self.x_root = XPathType(x_root + "//div[@class='MuiPickersClock-clock']")
        super().__init__(*args, **kwargs)
        self.pointer_len = self._get_pointer_length()

    @property
    def pointer(self) -> WebElement:
        return self.get_object(XPathType(self.x_root + "//div[contains(@class, 'MuiPickersClockPointer-pointer')]"))

    @property
    def pin(self) -> WebElement:
        return self.get_object(XPathType(self.x_root + "//div[@class='MuiPickersClock-pin']"))

    @property
    def thumb(self) -> WebElement:
        return self.get_object(XPathType(self.x_root + "//div[contains(@class, 'MuiPickersClockPointer-thumb')]"))

    def _get_pointer_length(self) -> float:
        pin_x, pin_y = self.pin.location['x'], self.pin.location['y']
        thumb = self.thumb
        thumb_x, thumb_y = thumb.location['x'], thumb.location['y']
        return math.sqrt((pin_x - thumb_x) ** 2 + (pin_y - thumb_y) ** 2)

    def _get_current_pin_degree(self) -> int:
        style = self.pointer.get_attribute("style")
        degree = int(re.findall("[0-9]+deg", style)[0][:-3])
        return degree

    def _move_thumb(self, direction, minutes=1) -> None:
        current_angle = math.radians(self._get_current_pin_degree())
        shift = direction * self.pointer_len * math.radians(self.ONE_MIN_DEGREE * minutes)
        thumb = self.thumb
        self._action_chains.click_and_hold(thumb).move_by_offset(
            shift * math.cos(current_angle),
            shift * math.sin(current_angle)).release().perform()

    def select_minutes(
            self,
            minute: int,
            get_minute_func: Callable[[], int]):
        if minute % 5:
            raise RuntimeError(f'{self}: minute must be aligned by 5')
        with allure.step(f'Select minute: {minute}'):
            log.info(f'Select minute: {minute}')
            if 0 > minute > 59:
                raise ValueError("Minutes should be within [0, 59] range!")

            minutes_now = self._get_current_pin_degree() // self.ONE_MIN_DEGREE
            # FYI: Regardless you can choose only time aligned by 5
            # though after opening "Click Page" there is set an abribrary minute
            # https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1694175894861359
            delta = minute - minutes_now
            log.debug(f'Minutes now: {minutes_now}, delta to {minute}: {delta}')

            if not delta:
                return
            direction = self.COUNTER_CLOCK_WISE if delta < 0 else self.CLOCK_WISE
            delta = math.ceil(abs(delta / 5)) + 12

            for ix in range(delta):
                self._move_thumb(direction, minutes=5 if ix else 1)
                log.debug(f'actual: {minute}, expected: {get_minute_func()}, try {ix} of {delta}')
                if get_minute_func() == minute:
                    break
            else:
                raise RuntimeError(f"Didn't set minute: {minute}")

    def select_hour(self, hour: int) -> None:
        with allure.step(f'Select hour: {hour}'):
            log.info(f'Select hour: {hour}')
            hour_elem = self.get_object(XPathType(self.x_root + f"//span[text()='{hour}']"))
            self._action_chains.move_to_element(hour_elem).click().perform()


class DatetimeDialog(BasePage):
    # TODO: use `Dialog` class
    def __init__(self, x_root: XPathType, *args, **kwargs):
        self.x_root = x_root
        super().__init__(*args, **kwargs)

    @property
    def button_year(self) -> WebElement:
        return self.get_desc_obj(XPathType("//button//h6[contains(text(), '202')]"), is_clickable=True)

    @property
    def button_date(self) -> WebElement:
        return self.get_desc_obj(XPathType("//button[descendant::h4]"), is_clickable=True)

    @property
    def buttons_time(self) -> tuple[WebElement, WebElement]:
        hour, minutes = self.get_objects(XPathType(f"{self.x_root}//div[h3[text()=':']]//button"), is_clickable=True)

        if hour.location['x'] > minutes.location['x']:
            hour, minutes = minutes, hour

        return hour, minutes

    @property
    def period(self) -> str:
        selected_element = self.get_desc_obj(XPathType('//h6[(text() = "AM" or text()="PM") and contains(@class, "Selected")]'))
        day_period = selected_element.text.lower()
        if day_period not in ('am', 'pm'):
            raise RuntimeError(f'Unknown period: {day_period}')
        return day_period

    @property
    def month(self) -> int:
        month_number = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        element = self.get_desc_obj(XPathType("//h4"))
        month_str = element.text.split()[0].lower()
        return month_number.index(month_str) + 1

    @property
    def button_am(self) -> WebElement:
        return self.get_desc_obj(XPathType("//button[descendant::*[text()='AM']]"), is_clickable=True)

    @property
    def button_pm(self) -> WebElement:
        return self.get_desc_obj(XPathType("//button[descendant::*[text()='PM']]"), is_clickable=True)

    @property
    @retry(ValueError, delay=2.0)
    def year(self) -> int:
        return int(self.button_year.text)

    @property
    def hour(self) -> int:
        return int(self.buttons_time[0].text)

    @property
    @retry(NoTextException)
    def minute(self) -> int:
        text = self.buttons_time[1].text
        if not text:
            raise NoTextException  # use already existing exception?
        return int(text)

    def open_year_page(self) -> YearDialog:
        self.button_year.click()
        return YearDialog(driver=self._driver, x_root=self.x_root)

    def open_calendar(self) -> CalendarPage:
        self.button_date.click()
        return CalendarPage(driver=self._driver, x_root=self.x_root)

    def open_hour_page(self) -> ClockPage:
        self.buttons_time[0].click()
        return ClockPage(driver=self._driver, x_root=self.x_root)

    def open_minutes_page(self) -> ClockPage:
        self.buttons_time[1].click()
        return ClockPage(driver=self._driver, x_root=self.x_root)

    def click_am(self) -> None:
        with allure.step('Click AM'):
            log.info('Click AM')
            self.button_am.click()

    def click_pm(self) -> None:
        with allure.step('Click PM'):
            log.info('Click PM')
            self.button_pm.click()

    def close(self) -> None:
        with allure.step(f'Close {self} with ESC button'):
            log.info(f'Close {self} with ESC button')
            self.root.send_keys(Keys.ESCAPE)
            self.wait_disappeared()

    def to_datetime(self) -> datetime:
        calendar = self.open_calendar()
        date_time = datetime(
            year=self.year,
            month=self.month,
            day=calendar.day,
            hour=self.hour if self.period == 'am' else self.hour + 12,
            minute=self.minute,
            tzinfo=consts.tz_pst,
        )
        log.info(f'{self} convert to datetime format: {date_time}')
        return date_time

    def set_datetime(self, dt_time: datetime) -> Self:
        with allure.step(f'Set date: {dt_time}'):
            log.info(f'Set date: {dt_time}')
            if dt_time.year != self.year:
                self.open_year_page().select_year(dt_time.year)

            calendar = self.open_calendar()

            if calendar.month_int != dt_time.month:
                calendar.select_month(dt_time.month)
                calendar.select_day(dt_time.day)
            elif dt_time.day != calendar.day:
                calendar.select_day(dt_time.day)

            hour = dt_time.hour
            if 0 <= hour < 12:
                if self.period != 'am':
                    self.click_am()
            if 12 <= hour < 24:
                if self.period != 'pm':
                    self.click_pm()
            hour = 12 if hour in (0, 12) else hour % 12
            if hour != self.hour:
                self.open_hour_page().select_hour(hour)

            # Pointer is spinning while switch from hours to minutes and vice versa
            time.sleep(1)
            # TODO: don't select minutes if it isn't necessary
            self.open_minutes_page().select_minutes(
                dt_time.minute,
                get_minute_func=lambda: self.minute,
            )
            return self
