from functools import partial
from typing import Callable
from typing import Iterable
from typing import Optional
from typing import Sequence
from urllib.parse import ParseResult
from urllib.parse import urlparse
import logging
import platform
import time

from bs4 import BeautifulSoup
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from typing_extensions import Self
import allure

from tools import UndefinedElementException
from tools import config
from tools import join_url
from tools.retry import retry
from tools.types import UrlType
from tools.types import XPathType
from tools.webdriver import CustomWebDriver
from tools.webdriver import WebElement
from tools.webdriver import find_elements
from tools.webdriver import get_main_js_workaround

log = logging.getLogger(__name__)

COLOR_NOTIFICATION = 'rgba(67, 160, 71, 1)'
COLOR_ERROR = 'rgba(211, 47, 47, 1)'
ERROR_TOOLTIP_PREFIX = 'Error:'


class NoElementException(TimeoutException):
    pass


class ElementIsNotClickableException(TimeoutException):
    pass


class PageDidNotLoaded(NoElementException):
    """ PageObject is looking for primary element when created by default """


class ElementStillExistsException(Exception):
    """Raised by `wait_disappeared` meethod"""


class InvalidElementException(Exception):
    pass


class LoaderException(Exception):
    """ Spinner doesn't disappear """


class NoClearButtonException(Exception):
    pass


class ErrorTooltipException(Exception):
    pass


class BasePage:
    path: str = ""  # path should start with '/' symbol
    x_root: XPathType = None  # type: ignore[assignment]

    def __init__(
            self,
            driver: CustomWebDriver,
            check_primary_element: bool = True,
            check_primary_element_timeout: int = 5,
            open_page: bool = False,
            min_root_opacity: float = 1.0,
    ):
        """
        `_primary_element` serves two purpuses:
        1) to make relative XPATHs. for example we have several 'live feed' widgets,
            we have to be able to locate web elements of each 'live feed' widget.
        2) to check that web element corresponding to page object is loaded successfully.
        """
        self._min_root_opacity = min_root_opacity
        self._driver = driver
        self._driver.implicitly_wait(0)

        if open_page:
            self.open_primary_url()
        if check_primary_element:
            try:
                self.wait_presence(timeout=check_primary_element_timeout)
            except NoElementException as exc:
                raise PageDidNotLoaded(str(self)) from exc

    @property
    def _primary_url(self) -> UrlType:
        if self.path.startswith("http"):
            return UrlType(self.path)
        return join_url(config.web_url, self.path)

    @property
    def driver(self) -> CustomWebDriver:
        return self._driver

    def __str__(self) -> str:
        return self.__class__.__name__

    @property
    def waiter(self) -> Callable:
        return partial(WebDriverWait, driver=self.driver)

    @property
    def bs4(self) -> BeautifulSoup:
        inner_html = self.root.get_attribute('innerHTML')
        return BeautifulSoup(inner_html, "lxml")

    @property
    def url(self) -> UrlType:
        return UrlType(self._driver.current_url)

    @property
    def parsed_url(self) -> ParseResult:
        return urlparse(self.url)

    @property
    def _action_chains(self) -> ActionChains:
        return ActionChains(self._driver)

    @property
    def root(self) -> WebElement:
        """ Element for primary xpath. Primary xpath is usually container of element """
        return self.get_object(self.x_root, min_opacity=self._min_root_opacity)

    @property
    def _snackbars(self) -> Iterable[WebElement]:
        snackbars = [t for t in self.get_objects(XPathType("//div[@id='notistack-snackbar']/.."), wait_presence=False) if t.text]
        log.info(f'{len(snackbars)} snackbars have been found: {[t.text for t in snackbars]}')
        return snackbars

    @property
    def hover_tooltip(self) -> str:
        element = self.get_object_or_none_no_wait(XPathType("//div[@class='UITooltipOld']"))
        if not element:
            element = self.get_object_or_none_no_wait(XPathType("//div[@class='UITooltip']"))
            if not element:
                raise NoElementException('No tooltip found')
            text = element.text
            log.info(f'Found new hover tooltip: "{text}"')
        else:
            text = element.text
            log.info(f'Found old hover tooltip: "{text}"')
        return text

    @property
    def tooltips(self) -> Sequence[str]:
        """
        Wait tooltip element and return it text.
        Returns 'None' if tooltip not found.
        """
        tooltips = []
        for bar in self._snackbars:
            color = bar.value_of_css_property("background-color")
            if color == COLOR_NOTIFICATION:
                tooltips.append(bar.text)
            elif color == COLOR_ERROR:
                log.warning(f'Snackbar with error: "{bar.text}"')
                tooltips.append(f'{ERROR_TOOLTIP_PREFIX} {bar.text}')
            else:
                raise RuntimeError(f'Unknown color {color} for tooltip: "{bar.text}"')
        return tooltips

    def wait(self, func: Callable, custom_exception=TimeoutException, *args, **kwargs):
        try:
            self.waiter(*args, **kwargs).until(func)
        except TimeoutException as exc:
            raise custom_exception from exc

    def assert_no_error_tooltips(self, other_tooltips: Sequence[str] = []):
        with allure.step('Assert there are no error tooltips'):
            tooltips = self.tooltips
            tooltips += other_tooltips  # type: ignore (Operator "+=" not supported for types "Sequence[str]" and "Sequence[str]")
            time.sleep(3)
            tooltips = set(tooltips) | set(self.tooltips)
            errors = tuple(filter(lambda e: e.startswith(ERROR_TOOLTIP_PREFIX), tooltips))
            if errors:
                raise ErrorTooltipException(', '.join(errors))

    def assert_tooltip(
            self,
            expected_tooltip: str,
            timeout: int = 6):
        # DUE TO https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1310#note_67153 we will have to get rid of checking tooltips
        with allure.step(f'Wait for tooltip: {expected_tooltip}'):
            log.info(f'Wait for tooltip: {expected_tooltip}')
            try:
                self.waiter(timeout=timeout, poll_frequency=0.5).until(
                    lambda x: expected_tooltip in self.tooltips)
            except TimeoutException as exc:
                raise RuntimeError(f'No tooltip: {expected_tooltip}') from exc

    @retry(StaleElementReferenceException, delay=0.5, tries=3)
    @retry(NoElementException, delay=1.5, tries=3)
    def _find_visible_element(self, xpath: XPathType):
        """
        Use case: There are several menu elements in DOM (all except one are hidden)
        """
        elements = self.get_objects(xpath)
        log.debug(f'Look for visible element among {len(elements)} elements for "{xpath}"')
        for element in elements:
            if element.is_displayed():
                return element
        raise NoElementException(f"No displayed elements found: '{xpath}'")

    def set_driver(self, another_driver: CustomWebDriver):
        self._driver = another_driver
        return self

    def refresh(self, *args, **kwargs) -> Self:
        with allure.step(f"Refresh {self.url}"):
            # TODO: wait spinner disappeared
            log.info(f"Refresh: {self.url}")
            self._driver.refresh()
            get_main_js_workaround(self._driver, url=None, refresh=True)
            time.sleep(2)
            self.wait_spinner_disappeared()
            obj = self.__class__(driver=self.driver, *args, **kwargs)
            return obj

    def open(self, url: UrlType) -> None:
        with allure.step(f"Open url {url}"):
            log.info(f"Open url {url}")
            get_main_js_workaround(self._driver, url)
            self.wait_spinner_disappeared()

    def open_primary_url(self):
        self.open(self._primary_url)
        return self

    def wait_disappeared(
            self,
            xpath: Optional[XPathType] = None,
            timeout: int = 10):
        xpath = xpath or self.x_root
        try:
            log.info(f'Wait disappeared: {xpath}')
            self.waiter(timeout=timeout, poll_frequency=1.0).until(
                lambda x: self.get_object_or_none_no_wait(xpath) is None)
        except TimeoutException as exc:
            raise ElementStillExistsException(self) from exc

    def wait_presence(
            self,
            xpath: Optional[XPathType] = None,
            timeout: int = 5,
            poll_frequency: float = 1.0,
            **kwargs) -> None:
        xpath = xpath or self.x_root
        try:
            self.waiter(timeout=timeout, poll_frequency=poll_frequency).until(
                lambda x: find_elements(self.driver, xpath))
        except TimeoutException as exc:
            raise NoElementException(f"Element wasn't shown: {xpath}") from exc

    def clear_input(self, element: WebElement) -> None:
        element.click()
        ctrl_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        element.send_keys(ctrl_key, 'a')
        element.send_keys(Keys.DELETE)

    def _wait_element_rendered(
            self,
            xpath: Optional[XPathType] = None,
            timeout: int = 3,
            poll_frequency: float = 0.25,
            min_opacity: float = 1.0):

        def _get_opacity(xpath: XPathType) -> float:
            element = self.get_object_no_wait(xpath)
            opacity = element.value_of_css_property("opacity")
            log.debug(f' - opacity = {opacity}')
            return float(opacity)

        xpath = xpath or self.x_root
        log.debug(f'Wait element rendered / has opacity at least {min_opacity}: {xpath}')
        try:
            self.waiter(timeout=timeout, poll_frequency=poll_frequency).until(
                lambda x: _get_opacity(xpath) >= min_opacity,
            )
        except TimeoutException as exc:
            raise NoElementException(f"Element wasn't rendered: '{xpath}': min opacity = {min_opacity}, actual opacity = {_get_opacity(xpath)}") from exc

    def _wait_element_clickable(
            self,
            xpath: Optional[XPathType] = None,
            timeout: int = 3):

        def is_enabled(xpath: XPathType) -> bool:
            element = self.get_object_or_none_no_wait(xpath)
            if element is None:
                return False
            return element.is_enabled()

        xpath = xpath or self.x_root
        log.debug(f'Wait element clickable/enabled: {xpath}')
        try:
            self.waiter(timeout=timeout, poll_frequency=0.5).until(
                lambda x: is_enabled(xpath) is True,
            )
        except TimeoutException as exc:
            raise ElementIsNotClickableException(str(self)) from exc

    def get_desc_obj(
            self,
            relative_xpath: XPathType,
            *args, **kwargs,
    ) -> WebElement:
        """
        get descendant object (use `self.x_root` as parent)
        """
        return self.get_object(XPathType(self.x_root + relative_xpath), *args, **kwargs)

    def get_object(
            self,
            xpath: XPathType,
            is_clickable: bool = False,
            wait_rendered: bool = True,
            timeout_presence: int = 3,
            timeout_clickable: int = 3,
            min_opacity: float = 1.0,
    ) -> WebElement:
        """
        Returns WebElement or raises NoElementException
        TODO: add parameters `wait_rendered`, `check_rendered`
        """
        self.wait_presence(xpath, timeout=timeout_presence)
        if wait_rendered:
            self._wait_element_rendered(xpath, timeout=2, min_opacity=min_opacity)
        if is_clickable:
            self._wait_element_clickable(xpath, timeout=timeout_clickable)
        return self.get_object_no_wait(xpath)

    def get_objects(
            self,
            xpath: XPathType,
            wait_presence: bool = False,
            *args, **kwargs,
    ) -> Sequence[WebElement]:
        if wait_presence:
            self.wait_presence(xpath, *args, **kwargs)
        return find_elements(self.driver, xpath)

    def get_object_no_wait(
            self,
            xpath: XPathType,
    ) -> WebElement:
        result = find_elements(self.driver, xpath)
        if not result:
            log.debug(f"no element with xpath: {xpath}")
            raise NoElementException(xpath)
        if len(result) > 1:
            raise UndefinedElementException(xpath)
        result = result[0]
        result.xpath = xpath  # type: ignore
        return result

    def get_object_or_none_no_wait(self, *args, **kwargs) -> Optional[WebElement]:
        try:
            return self.get_object_no_wait(*args, **kwargs)
        except NoElementException:
            return None

    def scroll_to_element(self, element: WebElement):
        self._driver.execute_script("arguments[0].scrollIntoView(true);", element)
        return self

    @retry(StaleElementReferenceException, tries=3)
    def is_spinner_showing(self, x_root: XPathType) -> bool:
        """
        Since 0.0.22 spinner doesn't disappear from DOM (it relates to shared widgets)
        thus we have to check whether spinner visible
        """
        spinner_new = self.get_object_or_none_no_wait(
            XPathType(x_root + "//*[name()='circle' and contains(@class, 'UILoaderIndicator')]"))
        spinners_old = self.get_objects(
            XPathType(x_root + "//div[@role='progressbar' and contains(@class, 'MuiCircularProgress')]"),
            wait_presence=False,
        )
        spinners_old = tuple(filter(lambda element: element.is_displayed(), spinners_old))
        # log.info(f' -   is_spinner_showing -> spinner_new={bool(spinner_new)} spinner_old={bool(spinners_old)}')
        spinners = [spinner for spinner in (spinner_new, *spinners_old) if spinner is not None]
        if not spinners:
            return False
        return any(s.is_displayed() for s in spinners)

    def wait_spinner_disappeared(
            self,
            comment: str = "",
            x_root: XPathType = XPathType(""),
            timeout_appeared: int = 2,
            timeout_disappeared: int = 25) -> Self:
        # sometimes str(self) fails since element has just disappeared
        # (for example in case `__str__` refers to `main` attribute)
        # TODO: find out the better way to fix it
        try:
            self_str = str(self)
        except NoElementException:
            self_str = type(self)

        if not comment:
            comment = self_str
        log.info(f'{comment}: check loader')
        try:
            self.waiter(timeout=timeout_appeared, poll_frequency=0.5).until(
                lambda x: self.is_spinner_showing(x_root=x_root) is True)
            log.info(f' - {comment}: loader detected')
        except TimeoutException:
            log.info(f' - {comment}: there is no loader')
            return self

        log.info(f' - {comment}: wait loader disappeared')
        self.wait(
            lambda x: self.is_spinner_showing(x_root=x_root) is False,
            LoaderException,
            timeout=timeout_disappeared,
            poll_frequency=0.5,
        )
        return self

    def set_network_conditions(
            self,
            latency: int = 0,
            offline: bool = False,
            download_throughput: int = 100,
            upload_throughput: int = 100):
        self._driver.set_network_conditions(  # type: ignore (Cannot access member "set_network_conditions" for type "CustomWebDriver")
            offline=offline,
            latency=latency * 1000,
            download_throughput=download_throughput * 1024,
            upload_throughput=upload_throughput * 1024,
        )
        time.sleep(2)


def is_element_exist(
    get_element: Callable[[], WebElement | BasePage],
    custom_exception=None,
) -> bool:
    from pages.button import NoButtonException

    exceptions_to_check = (PageDidNotLoaded, NoElementException, NoButtonException)
    if custom_exception:
        exceptions_to_check = exceptions_to_check + (custom_exception, )
    try:
        element = get_element()
    except exceptions_to_check:
        return False

    if isinstance(element, BasePage):
        return is_element_exist(lambda: element.root, custom_exception)

    if hasattr(element, '_element'):
        return is_element_exist(lambda: getattr(element, '_element'), custom_exception)

    try:
        return element.is_displayed()
    except (StaleElementReferenceException, WebDriverException):
        return False
