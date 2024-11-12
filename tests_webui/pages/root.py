from __future__ import annotations
import time
import logging
from typing import Optional
from typing import TYPE_CHECKING

import allure
from typing_extensions import Self

from tools import config
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools import join_url
from tools.retry import retry
from tools.types import FiltersType
from tools.types import IcoType
from tools.types import IdIntType
from tools.types import ImageTemplateType
from tools.types import XPathType
from tools.users import get_active_company
from tools.cameras import clear_cameras_cache
from tools.webdriver import WebElement

from pages.base_page import BasePage
from pages.base_page import NoElementException
from pages.confirm_dialog import ConfirmDialog
from pages.dashboard import DashboardPage
from pages.device_tree.device_tree_page import DeviceTreePage
from pages.feedback_dialog import FeedbackDialog
from pages.layout.layout_listbox import LayoutPage
from pages.object_card import ObjectCard
from pages.search import template_to_filter
from pages.search.panel_v2 import LeftSearchPanel
from pages.search.panel_v2 import RightSearchPanel
from pages.search.results_v2 import SearchResultPageV2
from pages.settings import SettingsNavigationPage
from pages.settings.help_page import HelpPage
from pages.switch_company import SwitchSystemDialog
from pages.user_settings import UserSettingsPanel
from pages.watchlists.watchlists import WatchListsTable

if TYPE_CHECKING:
    from pages.login import LoginPage

log = logging.getLogger(__name__)

ICO_DASHBOARD = IcoType('M535.384-586.154V-800H800v213.846H535.384ZM160-484.615V-800h264.616v315.385H160ZM535.384-160v-315.385H800V-160H535.384ZM160-160v-213.846h264.616V-160H160Zm30.769-355.385h203.077v-253.846H190.769v253.846Zm375.385 324.616h203.077v-253.846H566.154v253.846Zm0-426.154h203.077v-152.308H566.154v152.308ZM190.769-190.769h203.077v-152.308H190.769v152.308Zm203.077-324.616Zm172.308-101.538Zm0 172.308ZM393.846-343.077Z')


class FloatingPanel(BasePage):
    '''
    Appears at the upper-left corner after clicking "Avatar"
    and contains user details plus "User settings" and "Log out" button
    '''
    x_root = XPathType("//div[@data-floating-ui-portal]/div[@class='UITooltip']")

    @property
    def user_name(self) -> str:
        name_element = self.get_desc_obj(XPathType("//div[child::div[contains(@class, 'UIAvatar')]]/div[2]/div[1]"))
        return name_element.text

    @property
    def company_name(self) -> str:
        company_element = self.get_desc_obj(
            XPathType("//div[child::div[contains(@class, 'UIAvatar')]]/div[2]/div[3]"),
            min_opacity=0.5,
        )
        return company_element.text


class RootPage(BasePage):
    """
    Root page comprises of:
     - left panel
     - upper panel
     - dashboard
    """
    path = '/'
    x_root = XPathType("//div[child::div[@class='UILeftMenuBar']]")

    def __init__(self, *args, **kwargs):
        if 'check_primary_element_timeout' not in kwargs:
            kwargs['check_primary_element_timeout'] = 8
        self._x_left_menu = XPathType(self.x_root + "/div[contains(@class, 'UILeftMenuBar')]")
        super().__init__(*args, **kwargs)

    @property
    def _button_avatar_open_menu(self) -> WebElement:
        return self.get_desc_obj(XPathType("//div[child::div[contains(@class, 'UIAvatar')]]"))

    @property
    def layout(self) -> LayoutPage:
        return LayoutPage(driver=self._driver)

    @property
    def button_dashboard(self) -> IcoButton:
        return get_ico_button(
            self,
            ico=ICO_DASHBOARD,
            x_root=self._x_left_menu,
            button_tag=XPathType('a'),
            ix=0,
        )

    @property
    def button_dashboards(self) -> IcoButton:
        return get_ico_button(
            self,
            ico=ICO_DASHBOARD,
            x_root=self._x_left_menu,
            button_tag=XPathType('a'),
            ix=1,
        )

    @property
    def button_help(self) -> IcoButton:
        ico = IcoType('M484.043-273.923q10.572 0 18.111-7.966 7.538-7.967 7.538-18.539 0-9.803-7.581-17.726-7.582-7.923-18.154-7.923t-18.496 7.967q-7.923 7.966-7.923 17.769 0 10.572 7.967 18.495 7.966 7.923 18.538 7.923ZM463.615-403h32.077q.77-22.923 8.808-40.577 8.039-17.654 33.577-40.269 28.692-26.769 40.923-48.693 12.231-21.923 12.231-48.327 0-45.826-30.191-74.75-30.192-28.923-75.809-28.923-39.77 0-70.731 21.039-30.962 21.038-46.423 51.731l30.692 12.307q11.769-25.692 31.846-40.038 20.077-14.346 51.616-14.346 39.384 0 59.615 21.577t20.231 51.346q0 21.231-11.462 38.808-11.461 17.576-32.615 36.269-28.462 26-41.423 51.115-12.962 25.116-12.962 51.731Zm16.519 283q-74.442 0-139.794-28.339-65.353-28.34-114.481-77.422-49.127-49.082-77.493-114.373Q120-405.425 120-479.866q0-74.673 28.339-140.41 28.34-65.737 77.422-114.365 49.082-48.627 114.373-76.993Q405.425-840 479.866-840q74.673 0 140.41 28.339 65.737 28.34 114.365 76.922 48.627 48.582 76.993 114.257Q840-554.806 840-480.134q0 74.442-28.339 139.794-28.34 65.353-76.922 114.481-48.582 49.127-114.257 77.493Q554.806-120 480.134-120ZM480-150.769q137.385 0 233.308-96.039Q809.231-342.846 809.231-480q0-137.385-95.923-233.308T480-809.231q-137.154 0-233.192 95.923Q150.769-617.385 150.769-480q0 137.154 96.039 233.192Q342.846-150.769 480-150.769ZM480-480Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('a'))

    @property
    def button_settings(self) -> IcoButton:
        ico = IcoType('m413.384-120-16.153-114.461q-22.077-7-48.462-21.693-26.384-14.692-44.692-31.538l-105.693 47.846-66.846-118.616 94.154-69.769q-2-12.077-3.269-25.5-1.269-13.423-1.269-25.5 0-11.307 1.269-24.731 1.269-13.423 3.269-27.807l-94.154-70.539 66.846-116.308 104.924 46.308q20.615-16.846 45.461-31.154 24.846-14.307 47.692-21.077L413.384-840h133.232l16.153 115.231q25.154 9.307 47.808 21.961 22.654 12.654 43.038 30.5l108.77-46.308 66.077 116.308-97.231 71.616q3.538 13.846 4.423 26.5.885 12.654.885 24.192 0 10.769-1.27 23.308-1.269 12.538-4.038 27.923l96.462 70.307-66.847 118.616-107.231-48.615q-21.384 18.384-44.192 32.423-22.807 14.038-46.654 20.807L546.616-120H413.384Zm24.924-30.769h82.615L535.692-262q30.693-8 56.347-22.692 25.653-14.693 51.961-39.462l102.923 44.462 40-69.693L696-416.846q4-18.539 6.115-33.5 2.116-14.962 2.116-29.654 0-16.231-2-30.423-2-14.192-6.231-31.192l92.462-69-40-69.693-105.231 44.462q-19.154-21.385-49.692-40.039Q563-694.539 534.923-698l-13.231-111.231h-83.384l-12.462 110.462q-32.461 6.23-58.885 21.307-26.423 15.077-51.73 40.847l-103.693-43.693-40 69.693 90.923 66.692q-4.769 14.692-6.884 30.808-2.116 16.115-2.116 33.884 0 16.231 2.116 31.577 2.115 15.346 6.115 30.808l-90.154 67.461 40 69.693 102.923-43.693q24 24.77 50.808 39.462 26.808 14.692 59.808 22.692l13.231 110.462Zm39.384-233.846q40.154 0 67.77-27.616 27.615-27.615 27.615-67.769 0-40.154-27.615-67.769-27.616-27.616-67.77-27.616-39.384 0-67.384 27.616-28.001 27.615-28.001 67.769 0 40.154 28.001 67.769 28 27.616 67.384 27.616ZM480-480Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('a'))

    @property
    def button_watchlist(self) -> IcoButton:
        ico = IcoType('M480-496.615Zm-.136 392q-26.71 0-45.595-18.981-18.884-18.981-18.884-45.635h129.23q0 26.846-19.02 45.731-19.021 18.885-45.731 18.885Zm235.521-319.231v-124.616H590.769v-30.769h124.616v-124.615h30.769v124.615H870.77v30.769H746.154v124.616h-30.769ZM200-209.231V-240h64.615v-327.846q0-78.481 49.116-139.279Q362.846-767.923 440-781.462V-800q0-16.667 11.64-28.334Q463.28-840 479.91-840q16.629 0 28.359 11.666Q520-816.667 520-800v18.923q21.726 4.053 41.825 11.839 20.098 7.786 37.79 19.161-7.384 5.615-14.073 10.789-6.689 5.173-13.311 10.519-20.048-11.231-43.14-17.462-23.091-6.23-49.091-6.23-76.538 0-130.577 54.038-54.038 54.038-54.038 130.577V-240h369.23v-106.077q7.926 1.769 15.033 4.06 7.106 2.29 15.737 3.094V-240H760v30.769H200Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('a'))

    @property
    def button_device_tree(self) -> IcoButton:
        ico = IcoType('M341.077-190.769h278.615L587-320H373.769l-32.692 129.231Zm18.923-160h240q86.831 0 148.031-61.108t61.2-147.808q0-86.7-61.2-148.123-61.2-61.423-148.031-61.423H360q-86.831 0-148.031 61.108t-61.2 147.808q0 86.7 61.2 148.123 61.2 61.423 148.031 61.423Zm119.85-100q-44.927 0-77.004-32.227-32.077-32.227-32.077-77.154t32.227-77.004q32.227-32.077 77.154-32.077t77.004 32.227q32.077 32.227 32.077 77.154t-32.227 77.004q-32.227 32.077-77.154 32.077ZM258.896-616.846q9.335 0 16.796-7.444 7.462-7.444 7.462-17.645 0-9.45-7.444-16.796t-17.645-7.346q-9.45 0-16.796 7.444t-7.346 17.529q0 9.335 7.444 16.796 7.444 7.462 17.529 7.462ZM180-160v-30.769h129.308l32.923-129.692q-93.77-7.077-158-75.577Q120-464.538 120-560q0-100.286 69.857-170.143T360-800h240q100.286 0 170.143 69.857T840-560q0 95.462-64.231 163.962-64.23 68.5-158 75.577l32.923 129.692H780V-160H180Zm300-260q58.308 0 99.154-40.846T620-560q0-58.308-40.846-99.154T480-700q-58.308 0-99.154 40.846T340-560q0 58.308 40.846 99.154T480-420Zm0-140ZM341.077-190.769h278.615-278.615Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('a'))

    @property
    def button_search(self) -> IcoButton:
        ico = IcoType('M785.231-154.077 529.154-410.154q-29.696 26.829-69.261 40.914-39.564 14.086-79.585 14.086-95.585 0-161.793-66.028-66.208-66.029-66.208-161.001 0-94.971 66.029-161.125t160.941-66.154q94.911 0 161.509 66.065 66.599 66.066 66.599 160.961 0 41.205-14.769 80.821-14.77 39.615-41.231 69.23l256.308 255.077-22.462 23.231ZM380.077-385.923q82.66 0 139.599-56.731 56.939-56.731 56.939-139.654t-56.939-139.654q-56.939-56.73-139.599-56.73-82.853 0-139.926 56.73-57.074 56.731-57.074 139.654t57.074 139.654q57.073 56.731 139.926 56.731Z')
        return get_ico_button(
            self,
            ico,
            x_root=self._x_left_menu,
            button_tag=XPathType('div'),
            predicate="contains(@class, 'UILeftBarMenuButton') and "
        )

    @property
    def _button_switch_company(self) -> IcoButton:
        ico = IcoType('M80-200v-560h346.462v106.077h-30.77v-75.308H110.769v498.462h284.923v-75.308h30.77V-200H80Zm453.538 0v-106.077h30.77v75.308h88.923V-200H533.538Zm226.001 0v-30.769h89.692v-75.308H880V-200H759.539ZM533.538-653.923V-760h119.693v30.769h-88.923v75.308h-30.77Zm315.693 0v-75.308h-89.692V-760H880v106.077h-30.769ZM110.769-230.769v-498.462 498.462ZM680.692-360l-22-22 83.462-82.615H220.769v-30.77h521.385l-83.462-82.384 22-22L801-480 680.692-360Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('div'))

    @property
    def _button_logout(self) -> IcoButton:
        ico = IcoType('M215.384-160q-23.057 0-39.221-16.163Q160-192.327 160-215.384v-529.232q0-23.057 16.163-39.221Q192.327-800 215.384-800h265.154v30.769H215.384q-9.23 0-16.923 7.692-7.692 7.693-7.692 16.923v529.232q0 9.23 7.692 16.923 7.693 7.692 16.923 7.692h265.154V-160H215.384Zm455.231-190.384-23-21.462 92.77-92.769H367.692v-30.77h372.231l-92.769-92.769 22.231-22.231 130.615 131-129.385 129.001Z')
        return get_ico_button(self, ico, x_root=self._x_left_menu, button_tag=XPathType('div'))

    @property
    def dashboard(self) -> DashboardPage:
        return DashboardPage(driver=self._driver)

    def switch_to_default_layout(self) -> None:
        with allure.step(f'Switch to layout: "{LayoutPage.DEFAULT_LAYOUT_NAME}"'):
            self.layout.switch_to(LayoutPage.DEFAULT_LAYOUT_NAME)

    def open_primary_url(self, spinner_timeout: int = 40) -> Self:
        super().open_primary_url()
        self.wait_spinner_disappeared(timeout_disappeared=spinner_timeout)
        return self

    def search(
            self,
            template: ImageTemplateType,
            filters: Optional[FiltersType] = None,
            ignore_no_data: bool = False,
            fetch_more: bool = True,
            **kwargs,  # TODO: kwargs is FiltersType
    ) -> SearchResultPageV2:
        filters = {} if filters is None else dict(filters)
        filters.update(kwargs)
        filters.update(template_to_filter(template))

        with allure.step(f"{self}: perform v2 search of {template} by filters: {list(filters.keys())}"):
            log.info(f"{self}: perform v2 search of {template} by filters: {filters}")
            results = self.open_search_panel().\
                set_search_objective(template). \
                set_filters(**filters). \
                get_results(fetch_more=fetch_more, ignore_no_data=ignore_no_data)
            return results

    def search_count(self, *args, **kwargs) -> int:
        return self.search(*args, **kwargs).objects_count

    @allure.step("Open Dashboard page")
    def open_dashboard(self) -> DashboardPage:
        log.info("Open Dashboard")
        self.button_dashboard.click()
        self.wait_spinner_disappeared(timeout_disappeared=40)
        return DashboardPage(self._driver)

    @allure.step("Open Device Tree")
    def open_device_tree(self) -> DeviceTreePage:
        log.info("Open Device Tree")
        self.button_device_tree.click()
        self.wait_spinner_disappeared()
        time.sleep(2)  # seems like hiding left panel doesn't work right after "device tree" has been opened
        return DeviceTreePage(self._driver)

    @allure.step("Open Settings")
    def open_settings(self) -> SettingsNavigationPage:
        log.info("Open Settings")
        self.button_settings.click()
        self.wait_spinner_disappeared()
        return SettingsNavigationPage(self._driver)

    @allure.step("Open Help page")
    def open_help_page(self) -> HelpPage:
        self.button_help.click()
        self.wait_spinner_disappeared()
        return HelpPage(self._driver)

    @allure.step("Open V2 Advanced Search")
    def open_search_panel(self) -> RightSearchPanel | LeftSearchPanel:
        def is_panel_opened() -> bool:
            try:
                self.get_object_no_wait(SearchResultPageV2.x_root)
                return True
            except NoElementException:
                return False

        if is_panel_opened():
            log.info('Search panel is opened already')
            results = SearchResultPageV2(driver=self.driver)
            return results.filters_panel

        log.info("Open Search panel")
        time.sleep(0.5)  # prevent clicking "avatar"
                         # i know it sounds strange but you should trust me
        self.button_search.click()
        time.sleep(4)    # skip animation
        panel = RightSearchPanel(self.driver)
        return panel

    @retry(NoElementException)
    def open_avatar_menu(self) -> FloatingPanel:
        with allure.step('Open avatar menu'):
            log.info('Open avatar menu')
            self._button_avatar_open_menu.click()
            return FloatingPanel(driver=self.driver)

    def close_avatar_menu(self) -> None:
        with allure.step('Close avatar menu'):
            log.info('Close avatar menu')
            self._button_avatar_open_menu.click()
            self.wait(
                lambda x: self.get_object_or_none_no_wait(FloatingPanel.x_root) is None,
                RuntimeError('Avatar menu is still visible'),
                timeout=2,
                poll_frequency=0.2,
            )

    def logout(self) -> LoginPage:
        from pages.login import LoginPage

        with allure.step('Log out'):
            log.info("Log out")
            self._button_logout.click()
            ConfirmDialog(
                title="Log Out",
                confirm_label="Log out",
                driver=self.driver,
                is_mui=False,
                is_mui_confirm_button=False,
                is_mui_cancel_button=False,
            ).confirm()
            # self.driver.client = None  # TODO: should i set `client` to None??
            return LoginPage(driver=self.driver)

    @allure.step("Open 'Switch Company' dialog")
    def switch_company(self) -> SwitchSystemDialog:
        log.info("Open 'Switch Company' dialog")
        self._button_switch_company.click()
        clear_cameras_cache()
        return SwitchSystemDialog(driver=self.driver)

    def open_object(
            self,
            object_id: IdIntType,
            scroll_down: bool = False) -> ObjectCard:
        ''' Shortcut to open an object directly with with its url '''
        with allure.step(f'Open object card {object_id}'):
            log.info(f'Open object card {object_id}')
            active_company = get_active_company(self.driver.client)
            url = join_url(config.web_url, f'/appearances/{active_company.id}/{object_id}')
            self.open(url)  # `open` method invokes `wait_spinner_disappeared`
            card = ObjectCard(driver=self._driver)
            card.wait_spinner_disappeared(
                x_root=card.similar_objects_grid.x_root,
                comment='Wait similar objects loaded',
            )
            time.sleep(5)  # wait till pictures load (TODO: use more intelligent method to wait till all pictures load)
            if scroll_down:
                card.similar_objects_grid.fetch_more()
            return card

    def open_user_settings(self) -> UserSettingsPanel:
        with allure.step('Open user settings'):
            log.info('Open user settings')
            return self.open_settings(). \
                open_user_settings()

    def open_watchlists(self) -> WatchListsTable:
        with allure.step('Open watchlists'):
            log.info('Open watchlists')
            self.button_watchlist.click()
            return WatchListsTable(driver=self.driver)

    def open_feedback_dialog(self) -> FeedbackDialog:
        ico_exclamation_in_triangle = IcoType('M109.23-160 480-800l370.77 640H109.23Zm53.231-30.769h635.078L480-738.462 162.461-190.769Zm319.42-63.154q8.581 0 14.196-5.804 5.615-5.805 5.615-14.385t-5.804-14.196q-5.804-5.615-14.385-5.615-8.58 0-14.195 5.804-5.616 5.805-5.616 14.385t5.805 14.196q5.804 5.615 14.384 5.615Zm-15.573-84.846h30.769v-211.693h-30.769v211.693ZM480-464.615Z')
        with allure.step('Open feedback dialog'):
            log.info('Open feedback dialog')
            button_open_feedback = get_ico_button(
                self,
                ico_exclamation_in_triangle,
                x_root=self._x_left_menu,
                button_tag=XPathType('div'),
            )
            button_open_feedback.click()
            return FeedbackDialog(driver=self.driver)
