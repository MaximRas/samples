'''
move_to_element_with_offset() currently tries to use the top left corner of the element as the origin
in Selenium 4.3 it will use the in-view center point of the element as the origin.
'''

from __future__ import annotations
from argparse import Namespace
from abc import abstractmethod
from typing import Optional
from typing import Mapping
from typing import Sequence
from typing import Iterable
from typing import TYPE_CHECKING
from pathlib import Path
import json
import logging

import allure
from seleniumwire import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement as WebElementOrigin
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import consts
from tools.retry import retry
from tools.types import XPathType
from tools.types import UrlType
if TYPE_CHECKING:
    from tools.users import ApiClient
    from seleniumwire.request import Request

log = logging.getLogger(__name__)
logging.getLogger('seleniumwire').setLevel(logging.ERROR)
logging.getLogger('hpack').setLevel(logging.ERROR)

# TODO: set timeouts https://stackoverflow.com/questions/32276654/setting-page-load-timeout-in-selenium-python-binding


class WebElement(WebElementOrigin):
    def __init__(self, *args, **kwargs):
        self.xpath: Optional[XPathType] = None
        super().__init__(*args, **kwargs)


class FailedToLoadMainJS(Exception):
    pass


class UncaughtJSError(Exception):
    pass


class CustomWebDriver(WebDriver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: ApiClient = None
        self.requests: Iterable[Request] = []
        self.is_just_created: Optional[bool] = None
        raise NotImplementedError  # only for type hinting

    @abstractmethod
    def delete_network_conditions(self):
        raise NotImplementedError

    @property
    def client(self) -> ApiClient:
        return self._client

    @client.setter
    def client(self, new_value: ApiClient):
        self._client = new_value


def get_body(req: Request) -> Optional[Mapping]:
    if not hasattr(req, 'body'):
        return None
    decoded_body = req.body.decode().strip()
    if not decoded_body:
        return None
    return json.loads(decoded_body)


class LastRequestsContext:
    def __init__(self, driver: CustomWebDriver):
        self._driver = driver
        del self._driver.requests

    def __enter__(self):
        def filter_reqests(
                requests: Iterable[Request],
                url=Optional[UrlType]) -> Iterable[Request]:
            result = []
            for req in requests:
                if url is not None and str(url) in req.url:
                    result.append(req)
            return result

        def _get_last_req_func(*args, **kwargs) -> Iterable[Request]:
            req_to_filter = self._driver.requests
            del self._driver.requests
            return filter_reqests(req_to_filter, *args, **kwargs)

        return _get_last_req_func

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def collect_browser_logs(
        driver: CustomWebDriver,
        check_uncaught_errors: bool = False) -> Iterable[str]:
    log.debug('Collect browser logs')
    exceptions = {
        'googletagmanager',
        'Write permission denied',
        'sentry.io',
    }
    logs = []
    for entry in [entry for entry in driver.get_log('browser') if entry['level'] == 'SEVERE']:
        for exception_str in exceptions:
            if exception_str in entry['message']:
                break
        else:
            log.error(f'browser console: {entry["message"]}')
            logs.append(entry['message'])

    if check_uncaught_errors:
        for message in logs:
            if 'Uncaught TypeError:' in message:
                raise UncaughtJSError(message)

            if 'WebSocket' in message:
                raise UncaughtJSError(message)

            if 'Unprocessable Entity' in message:
                raise UncaughtJSError(message)
    return logs


def create_chrome_webdriver(
        is_headless: bool,
        profile_dir: Path,
) -> CustomWebDriver:
    """ FYI: https://peter.sh/experiments/chromium-command-line-switches/ """
    options = webdriver.ChromeOptions()
    if is_headless:
        options.add_argument("--headless")
    options.add_argument("--start-maximized")        # https://stackoverflow.com/a/26283818/1689770
    options.add_argument("--enable-automation")
    options.add_argument("--no-sandbox")             # chromium sandbox not working in docker https://stackoverflow.com/a/50725918/1689770
    options.add_argument("--disable-gpu")            # https://stackoverflow.com/questions/51959986/how-to-solve-selenium-chromedriver-timed-out-receiving-message-from-renderer-exc
    options.add_argument("--disable-dev-shm-usage")  # https://stackoverflow.com/questions/53902507/unknown-error-session-deleted-because-of-page-crash-from-unknown-error-cannot and https://stackoverflow.com/a/50725918/1689770
    # TODO: add_argument("--auto-open-devtools-for-tabs")
    # options.page_load_strategy = 'normal', 'eager' or None

    if profile_dir:
        log.info(f'Set chrome profile dir: "{profile_dir}"')
        options.add_argument(f"--user-data-dir={profile_dir}")
    chrome = webdriver.Chrome(options=options)
    # chrome.set_page_load_timeout(20)
    return chrome  # type: ignore # Expression of type "Chrome | WebDriver" cannot be assigned to return type "CustomWebDriver"


def create_gecko_webdriver(is_headless: bool) -> CustomWebDriver:
    options = webdriver.FirefoxOptions()
    if is_headless:
        options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.maximize_window()
    return driver  # type: ignore # Expression of type "Firefox | WebDriver" cannot be assigned to return type "CustomWebDriver"


def create_webdriver(
        session_options: Namespace,
        is_another_driver: bool = False,
) -> CustomWebDriver:
    with allure.step(f"Create webdriver: {session_options.webdriver}"):
        log.info(f"Create webdriver: {session_options.webdriver}")
        if session_options.webdriver == "chrome":
            if session_options.profile_dir:
                if is_another_driver:
                    profile_dir = session_options.profile_dir.parent / (session_options.profile_dir.name + '_another')
                else:
                    profile_dir = session_options.profile_dir
            else:
                profile_dir = None
            driver = create_chrome_webdriver(
                is_headless=session_options.headless,
                profile_dir=profile_dir,
            )
        elif session_options.webdriver == "gecko":
            driver = create_gecko_webdriver(is_headless=session_options.headless)
        else:
            raise ValueError(f"Unknown driver type: {session_options.webdriver}")

        if session_options.headless:
            driver.set_window_size(*consts.RESOLUTION)
    return driver


@retry(FailedToLoadMainJS, tries=4, delay=6)
def get_main_js_workaround(
        driver: CustomWebDriver,
        url: UrlType,
        refresh: bool = False) -> None:
    '''
    FYI:
     - https://metapix-workspace.slack.com/archives/C043WBPF6AE/p1685966168742599
     - https://metapix-workspace.slack.com/archives/C05239V101L/p1685965488050879
     - https://metapix-workspace.slack.com/archives/C052CC71TEY/p1685534360457119
     - https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1685540820835439
     - https://gitlab.dev.metapixai.com/metapix-cloud/miscellaneous/admin/-/issues/207
    '''
    if url:
        driver.get(url)
    if refresh:
        driver.refresh()
    for error_message in collect_browser_logs(driver):
        if 'Failed to load resource' in error_message and 'static/js/main' in error_message:
            raise FailedToLoadMainJS(error_message)


def find_elements(
        driver_or_element: CustomWebDriver | WebElement,
        xpath: XPathType,
) -> Sequence[WebElement]:
    found_elements = driver_or_element.find_elements(By.XPATH, xpath)
    for ix, element in enumerate(found_elements):
        if isinstance(driver_or_element, WebElementOrigin):
            element.parent_element = driver_or_element
        # TODO: explain
        element.xpath_list = f'{xpath}[{ix+1}]'   # type: ignore
        element.xpath = f'({xpath})[{ix+1}]'      # type: ignore
    return found_elements  # type: ignore


def find_element(
        driver_or_element: CustomWebDriver | WebElement,
        xpath: XPathType,
) -> WebElement:
    found_elements = find_elements(driver_or_element, xpath)

    if len(found_elements) == 0:
        raise NoSuchElementException
    if len(found_elements) > 1:
        log.warning(f'  Found more that one ({len(found_elements)}) of {xpath}')

    element = found_elements[0]
    if isinstance(driver_or_element, WebElementOrigin):
        element.parent_element = driver_or_element
    element.xpath = xpath
    return element


class TempTab:
    ''' https://www.selenium.dev/documentation/webdriver/interactions/windows/ '''
    def __init__(self, driver: CustomWebDriver):
        with allure.step(f'Create a temporary new tab for {self._driver}'):
            self._driver = driver
            self._original_window = self._driver.current_window_handle

            log.info(f'Create a temporary new tab for {self._driver}')
            window_handles_before = self._driver.window_handles
            self._create_tab()
            window_handles_after = self._driver.window_handles
            if len(window_handles_after) != len(window_handles_before) + 1:
                raise RuntimeError

            # look for a new window handle
            for handle in window_handles_after:
                if handle != self._original_window:
                    handle_to_switch = handle
                    break
            else:
                raise RuntimeError

            log.info(f'Switch to handle {handle_to_switch}')
            self._driver.switch_to.window(handle_to_switch)

    def _create_tab(self) -> None:
        self._driver.execute_script("window.open('');")

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        log.info('Close current tab and restore default')
        self._driver.close()
        self._driver.switch_to.window(self._original_window)


def do_not_request_deleted_companies(request: Request):
    if not request.path.endswith('/v1/user/companies'):
        return
    log.warning(f'repalce body of request {request.path}')
    request.body = b'{"filters":{"with_deleted":false}}'
    request.headers.replace_header('Content-Length', len(request.body))
