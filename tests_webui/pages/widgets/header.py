from collections import namedtuple
import logging
import time
from typing import Callable

from selenium.webdriver.common.keys import Keys
from typing_extensions import Self
import allure

import consts
from consts import ICO_BUTTON_BAR_CHART
from consts import ICO_BUTTON_LINE_CHART
from tools import attribute_to_bool
from tools import wait_objects_arrive
from tools.color import Color
from tools.getlist import GetList
from tools.ico_button import IcoButton
from tools.ico_button import get_ico_button
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement
from tools.webdriver import find_element
from tools.webdriver import get_main_js_workaround

from pages.base_page import BasePage
from pages.base_page import PageDidNotLoaded
from pages.base_page import is_element_exist
from pages.button import IconButton
from pages.checkbox import ICO_CHECKED
from pages.checkbox import ICO_UNCHECKED
from pages.confirm_dialog import ConfirmDialog
from pages.sharable_link_dialog import SharableLinkDialog
from pages.widgets.base_widget import AutoRefreshStateException
from pages.widgets.settings import WidgetSettings
from pages.widgets.shared import BaseSharedWidget
from pages.widgets.shared import OpenSharedWidgetException

log = logging.getLogger(__name__)


class WidgetHeaderButtonStateException(Exception):
    pass


WidgetBox = namedtuple("WidgetBox", "x0 y0 x1 y1 width height")
ADJUST_MENU_XPATH = XPathType("//ul[@role='menu']")
ICO_BUTTON_AUTOREFRESH = IcoType('M195.435-314.608q-24.522-38.826-34.783-79.848-10.261-41.022-10.261-84.674 0-133.261 96.478-230.87 96.479-97.609 229.174-97.609h43l-73.217-73.782 43.522-43.522L645.696-768 489.348-611.652l-44.522-43.957 72.217-72.782h-39.869q-101.348 0-174.456 73.674-73.109 73.674-73.109 175.587 0 30.695 6.065 57.826 6.066 27.13 15.761 50.695l-56 56.001ZM468.652-32.086 312.304-188.435l156.348-157.478 44.087 44.087-73.782 73.217h43.869q101.348 0 174.456-73.674 73.109-73.674 73.109-176.152 0-30.13-5.848-57.261-5.848-27.13-16.978-50.695l56.565-56.001q23.957 39.391 34.718 80.131 10.761 40.739 10.761 83.826 0 133.826-96.478 231.718-96.479 97.891-228.609 97.891h-45.565l73.782 73.217-44.087 43.522Z')
ICO_BUTTON_MORE = IcoType('M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z')
ICO_BUTTON_CONFIRM_TITLE = IcoType('M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z')
ICO_BUTTON_ADJUST_MENU = IcoType('M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z')
ICO_AUTOREFRESH_INFO = IcoType('M446.782-273.782h72.436V-520h-72.436v246.218Zm33.25-311.739q17.642 0 29.544-11.638 11.903-11.638 11.903-28.841 0-18.689-11.92-30.584t-29.541-11.895q-18.257 0-29.877 11.895-11.62 11.895-11.62 30.301 0 17.557 11.935 29.159 11.934 11.603 29.576 11.603Zm.312 519.652q-86.203 0-161.506-32.395-75.302-32.395-131.741-88.833-56.438-56.439-88.833-131.738-32.395-75.299-32.395-161.587 0-86.288 32.395-161.665t88.745-131.345q56.349-55.968 131.69-88.616 75.34-32.648 161.676-32.648 86.335 0 161.779 32.604t131.37 88.497q55.926 55.893 88.549 131.452 32.623 75.559 32.623 161.877 0 86.281-32.648 161.575-32.648 75.293-88.616 131.478-55.968 56.186-131.426 88.765-75.459 32.58-161.662 32.58Zm.156-79.218q139.239 0 236.826-97.732 97.587-97.732 97.587-237.681 0-139.239-97.4-236.826-97.399-97.587-237.796-97.587-139.021 0-236.826 97.4-97.804 97.399-97.804 237.796 0 139.021 97.732 236.826 97.732 97.804 237.681 97.804ZM480-480Z')


ICO_TO_SLUG = {
    ICO_AUTOREFRESH_INFO: "AUTOREFRESH INFO",
    ICO_BUTTON_ADJUST_MENU: "ADJUST",
    ICO_BUTTON_AUTOREFRESH: "AUTOREFRESH",
    ICO_BUTTON_BAR_CHART: "BAR CHART",
    ICO_BUTTON_CONFIRM_TITLE: "CONFIRM",
    ICO_BUTTON_LINE_CHART: "LINE CHART",
    ICO_BUTTON_MORE: "MORE",
    consts.ICO_CLOSE0: "CANCEL",
    consts.ICO_SQUARE: 'ROI',
    consts.ICO_ZOOM_IN: 'ZOOM IN',
}

BUTTON_ICO_TO_TITLE = {
    ICO_AUTOREFRESH_INFO: "Autorefresh info",
    ICO_BUTTON_ADJUST_MENU: "More",
    ICO_BUTTON_AUTOREFRESH: "Auto refresh",
    ICO_BUTTON_BAR_CHART: "Bar chart",
    ICO_BUTTON_CONFIRM_TITLE: "Confirm title",
    ICO_BUTTON_LINE_CHART: "Line chart",
    ICO_BUTTON_MORE: "More",
    consts.ICO_CLOSE0: "Cancel title",
    consts.ICO_SQUARE: 'ROI',
    consts.ICO_ZOOM_IN: 'Zoom in',
}


def _check_button_is_not_exist(func: Callable, comment: str) -> None:
    if is_element_exist(func):
        raise RuntimeError(f'{comment}: still exists')


class WidgetHeaderIconButton(IconButton):
    '''
    It is not a just ico button.
     - Widget header ico buttons may be highlighted
     - Widget header ico buttons have two states: "on" and "off"
     - Ico buttons just for clicking
    '''
    COLORS_ACTIVE = [
        consts.SHARPVUE_THEME_BUTTON_ACTIVE,
        consts.ORANGE_THEME_BUTTON_ACTIVE,
        consts.BLUE_THEME_BUTTON_ACTIVE,
    ]
    COLORS_INACTIVE = [
        consts.ORANGE_THEME_BUTTON_INACTIVE,
        consts.BLUE_THEME_BUTTON_INACTIVE,
        consts.COLOR_WHITE,
    ]

    def __init__(self, ico, title, x_root="", *args, **kwargs):
        self._ico = ico
        x_root = x_root + f"//div[contains(@class, 'Tooltip') and descendant::*[name()='path' and @d='{self._ico}']]"
        super().__init__(
            x_root=x_root,
            title=title,
            min_root_opacity=0.25,
            *args, **kwargs,
        )

    def __str__(self):
        return f'Button "{self.slug}"'

    @property
    def slug(self):
        return ICO_TO_SLUG[self._ico]

    def is_highlighted(self):
        """ Check button color """
        with allure.step(f"Check status of {self}"):
            element = find_element(self.root, XPathType(".//*[name()='svg']"))
            color = Color(element.value_of_css_property("fill"))
            log.debug(f"Check status of {self} by {color}")
            if color in [Color(c) for c in self.COLORS_ACTIVE]:
                return True
            if color in [Color(c) for c in self.COLORS_INACTIVE]:
                return False
            return None

    def switch_on(self):
        if self.is_highlighted() is not False:
            raise WidgetHeaderButtonStateException(f'{self} autorefresh is enabled')
        self.click()
        self.wait(
            lambda x: self.is_highlighted() is True,
            WidgetHeaderButtonStateException(f'{self} autorefresh is still disabled'),
            timeout=6, poll_frequency=1.5,
        )
        return self

    def switch_off(self):
        if self.is_highlighted() is not True:
            raise WidgetHeaderButtonStateException(f'{self} autorefresh is disabled')
        assert self.is_highlighted() is True
        self.click()
        self.wait(
            lambda x: self.is_highlighted() is False,
            WidgetHeaderButtonStateException(f'{self} autorefresh is still enabled'),
            timeout=6, poll_frequency=1.5,
        )
        return self


class AdjustMenuCheckbox:
    def __init__(self, element, parent):
        self._element = element
        self._parent = parent

    def __str__(self):
        return f'Adjust menu checkbox: {self.name}'

    @property
    def name(self):
        return self._element.text

    @property
    def _input(self):
        return find_element(self._element, XPathType(".//input"))

    def toggle(self):
        with allure.step(f'Toggle {self}'):
            log.info(f'Toggle {self}')
            self._input.click()

    def is_checked(self):
        is_checked_dom = attribute_to_bool(self._input, 'checked')
        ico = find_element(self._element, XPathType(".//*[name()='path']")).get_attribute("d")
        if ico == ICO_CHECKED:
            is_checked_ico = True
        elif ico == ICO_UNCHECKED:
            is_checked_ico = False
        else:
            raise RuntimeError(f'{self}: unknown ico')

        assert is_checked_dom == is_checked_ico
        return bool(is_checked_dom)


class WidgetHeader(BasePage):
    X_WIDGET_TEMPLATE = "//div[contains(@class, 'react-grid-item') and (descendant::input[@value='{title}'] or descendant::h6='{title}')]"

    def __init__(self, title, *args, **kwargs):
        self._title = title
        super().__init__(*args, **kwargs)
        self.scroll_to_element(self.get_object_no_wait(self.x_root))
        self._x_header = self.x_root + "//div[child::div[contains(@class, 'UIDraggable')]]"

    def __str__(self):
        return self.title

    def refresh(self) -> Self:
        obj = super().refresh(title=self._title)
        time.sleep(1)  # timeslice buttons aren't available without this delay
        return obj

    @property
    def state(self):
        from pages.widgets import get_base_state

        return get_base_state(self, is_shared=False)

    @property
    def _header_icons(self):
        return self.get_objects(
            self.x_root +
            "//div[contains(@class, 'UIDraggable')]"
            "//*[name()='path']"
        )

    @property
    def header_buttons(self):
        buttons = []
        for ico_element in self._header_icons:
            buttons.append(
                self._init_header_ico_button(ico_element.get_attribute('d'))
            )
        if not buttons:
            raise RuntimeError(f'{self}: no header buttons')
        return buttons

    @property
    def header_buttons_schema(self):
        ''' Simple schema. Only slugs '''
        return [btn.slug for btn in self.header_buttons]

    @property
    def title(self):
        return self._title

    @property
    def x_root(self) -> XPathType:  # type: ignore[reportIncompatibleVariableOverride]
        return XPathType(self.X_WIDGET_TEMPLATE.format(title=self.title))

    @property
    def header_title(self):
        return self.get_object(self.x_root + "//h6")

    @property
    def header_text(self):
        return self.header_title.text

    def _init_header_ico_button(self, ico, *args, **kwargs) -> IcoButton | WidgetHeaderIconButton:
        if ico in (ICO_BUTTON_CONFIRM_TITLE, consts.ICO_CLOSE0, ICO_BUTTON_MORE):
            button = get_ico_button(
                page=self,
                ico=ico,
                x_root=self._x_header,
                button_tag=XPathType('button'),
                name=ICO_TO_SLUG[ico],
            )
            return button

        return WidgetHeaderIconButton(
            title=BUTTON_ICO_TO_TITLE[ico],
            ico=ico,
            x_root=self._x_header,
            driver=self._driver,
            *args, **kwargs,
        )

    @property
    def button_zoom_in(self):
        '''
        available only for live feed widget
        https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1299
        '''
        return self._init_header_ico_button(consts.ICO_ZOOM_IN)

    @property
    def _button_confirm_title(self):
        return self._init_header_ico_button(ICO_BUTTON_CONFIRM_TITLE)

    @property
    def _button_cancel_title(self):
        return self._init_header_ico_button(consts.ICO_CLOSE0)

    @property
    def button_filter(self):
        raise NotImplementedError

    @property
    def button_autorefresh(self):
        return self._init_header_ico_button(ICO_BUTTON_AUTOREFRESH)

    @property
    def label_autorefresh_info(self):
        ''' value widget only '''
        return self._init_header_ico_button(ICO_AUTOREFRESH_INFO)

    @property
    def button_more(self):
        return self._init_header_ico_button(ICO_BUTTON_MORE)

    @property
    def button_adjust_menu(self):
        return self._init_header_ico_button(ICO_BUTTON_ADJUST_MENU)

    @property
    def button_more_share(self):
        return self._find_visible_element('//span[text()="Share"]')

    @property
    def button_more_settings(self):
        return self._find_visible_element('//span[text()="Settings"]')

    @property
    def button_more_delete(self):
        return self._find_visible_element('//span[text()="Delete"]')

    @property
    def box(self) -> WidgetBox:
        loc = self.root.location
        size = self.root.size
        return WidgetBox(
            x0=loc["x"],
            y0=loc["y"],
            width=size["width"],
            height=size["height"],
            x1=loc["x"] + size["width"],
            y1=loc["y"] + size["height"],
        )

    @property
    def resizable_handle(self) -> WebElement:
        return self.get_object(self.x_root + "//span[contains(@class, 'react-resizable-handle')]")

    def _change_title(self, new_title: str) -> None:
        with allure.step(f'Change title "{self}" -> "{new_title}"'):
            log.info(f'Change title "{self}" -> "{new_title}"')
            self._title = new_title

    def _change_adjust_menu(self, label: str, desired_state: bool) -> None:
        with allure.step(f'{self}: change adjust menu: "{label}" {not desired_state} -> {desired_state}'):
            log.info(f'{self}: change adjust menu: "{label}" {not desired_state} -> {desired_state}')
            self._open_adjust_menu()
            checkbox = self._get_adjust_menu_checkboxes().get(label)
            assert checkbox.is_checked() is not desired_state
            checkbox.toggle()
            self.wait_spinner_disappeared()
            checkbox = self._get_adjust_menu_checkboxes().get(label)
            assert checkbox.is_checked() is desired_state
            self._close_adjust_menu()

    def _get_adjust_menu_checkboxes(self):
        elements_checkboxes = self.get_objects(ADJUST_MENU_XPATH + "/li")
        if not elements_checkboxes:
            raise RuntimeError('No checkboxes have been found in "Adjust" menu')
        return GetList([AdjustMenuCheckbox(e, self) for e in elements_checkboxes])

    def _open_adjust_menu(self):
        with allure.step(f'{self}: open adjust menu'):
            log.info(f'{self}: open adjust menu')
            self.button_adjust_menu.click()
            self.waiter(timeout=2, poll_frequency=0.5).until(
                lambda x: self.get_objects(ADJUST_MENU_XPATH)
            )
            time.sleep(0.5)

    def _close_adjust_menu(self):
        with allure.step(f'{self}: close adjust menu'):
            self.get_object(ADJUST_MENU_XPATH).send_keys(Keys.ESCAPE)
            self.waiter(timeout=2, poll_frequency=0.5).until(
                lambda x: not self.get_objects(ADJUST_MENU_XPATH)
            )

    def _open_more_menu(self):
        with allure.step('Open "More" menu'):
            log.info('Open "More" menu')
            self.button_more.click()
            time.sleep(0.5)

    def open_settings(self) -> WidgetSettings:
        with allure.step(f"{self}: open settings"):
            log.info(f"{self}: open settings")
            self._open_more_menu()
            self.button_more_settings.click()
            dialog = WidgetSettings(parent=self, driver=self._driver)
            time.sleep(3)
            return dialog

    def open_share_dialog(self) -> SharableLinkDialog:
        with allure.step(f"{self}: open 'Share widget' dialog"):
            log.info(f"{self}: open 'Share widget' dialog")
            self._open_more_menu()
            self.button_more_share.click()
            return SharableLinkDialog(driver=self._driver)

    @allure.step("Open shared widget")
    def share(self, another_driver, return_page=None):
        with allure.step(f"{self}: share widget"):
            log.info(f"{self}: share widget")
            share_widget_dialog = self.open_share_dialog()
            link = share_widget_dialog.value
            share_widget_dialog.close_with_esc()
            log.info(f"{self} shared link: {link}")

            for parent_class in self.__class__.__bases__:
                if not issubclass(parent_class, WidgetHeader):
                    break
            else:
                raise RuntimeError(f"Not found widget class for {self}")
            SharedWidget = type("SharedWidget", (BaseSharedWidget, parent_class), {})

            get_main_js_workaround(another_driver, link)
            if return_page:
                page = return_page(driver=another_driver)
            else:
                try:
                    page = SharedWidget(driver=another_driver, check_primary_element_timeout=10)
                except PageDidNotLoaded as exc:
                    raise OpenSharedWidgetException(self) from exc
                wait_objects_arrive()
            page.wait_spinner_disappeared()
            time.sleep(3)
            return page

    def open_delete_dialog(self) -> ConfirmDialog:
        with allure.step(f"{self}: open delete dialog"):
            log.info(f"{self}: open delete dialog")
            self._open_more_menu()
            self.button_more_delete.click()
            return ConfirmDialog(title="Delete widget", driver=self._driver)

    def delete(self):
        # TODO: check tooltips: positive
        with allure.step(f"{self}: delete"):
            log.info(f"{self}: delete")
            self.open_delete_dialog().confirm()
            tooltips_after_deletion = self.tooltips
            self.wait_disappeared(timeout=5)
            self.assert_no_error_tooltips(other_tooltips=tooltips_after_deletion)

    def set_filters(self, *args, **kwargs):
        settings = self.open_settings()
        settings.set_filters(*args, **kwargs)
        settings.apply()

    def enable_autorefresh(self, delay=2):
        with allure.step(f"{self}: enable autorefresh"):
            log.info(f"{self}: enable autorefresh")
            try:
                self.button_autorefresh.switch_on()
            except WidgetHeaderButtonStateException:
                raise AutoRefreshStateException
            time.sleep(delay)
        return self

    def disable_autorefresh(self):
        with allure.step(f"{self}: disable autorefresh"):
            log.info(f"{self}: disable autorefresh")
            try:
                self.button_autorefresh.switch_off()
            except WidgetHeaderButtonStateException as exc:
                raise AutoRefreshStateException from exc
            time.sleep(2)
        return self

    def toggle_autorefresh(self):
        if self.is_autorefresh_enabled() is True:
            self.disable_autorefresh()
        elif self.is_autorefresh_enabled() is False:
            self.enable_autorefresh()
        else:
            raise RuntimeError
        return self

    def is_autorefresh_enabled(self) -> bool:
        return self.button_autorefresh.is_highlighted()

    def assert_autorefresh_enabled(self):
        time.sleep(1)
        if self.is_autorefresh_enabled() is not True:
            raise AutoRefreshStateException

    def assert_autorefresh_disabled(self):
        time.sleep(1)
        if self.is_autorefresh_enabled() is not False:
            raise AutoRefreshStateException

    def get_available_space(self) -> tuple[int, int]:
        ''' Get available space to resize '''
        return tuple([
            self._driver.get_window_rect()["width"] - self.box.x1,
            self._driver.get_window_rect()["height"] - self.box.y1,
        ])

    def resize(self, dx=0, dy=0) -> WidgetBox:
        old_box = self.box
        with allure.step(f"{self}: resize {dx=}, {dy=}"):
            log.info(f"{self}: resize {dx=}, {dy=}")
            self._action_chains.\
                click_and_hold(self.resizable_handle).\
                move_by_offset(dx, dy).\
                release().perform()
        # since 0.48 resizing leads to updating live feed widget content (refreshing widget)
        if self.type == consts.WIDGET_LIVE_FEED:
            self.wait_spinner_disappeared(x_root=self.x_root)
        time.sleep(2)  # resizing a widget leads to rendering. wait until the widget is being rendered
        return old_box

    def expand(self):
        """
        Expand widget to fill entire screen
        """
        dx = self._driver.get_window_rect()["width"] - self.box.x1
        self.resize(dx=dx)
        return self

    def drag_and_drop(self, dx, dy):
        with allure.step(f'{self} drag and drop with header by {dx=} {dy=}'):
            log.info(f'{self} drag and drop with header by {dx=} {dy=}')
            draggable = self.get_desc_obj("//div[contains(@class, 'UIDraggable')]")
            # width, height = draggable.size['width'], draggable.size['height']
            self.scroll_to_element(draggable)
            self._action_chains. \
                move_to_element_with_offset(draggable, 0, 0). \
                click_and_hold(). \
                move_by_offset(dx, dy). \
                release(). \
                perform()
            time.sleep(3)
            return self

    def enter_edit_title_mode(self):
        with allure.step(f"{self}: click header to edit title"):
            log.info(f"{self}: click header to edit title")
            self.header_title.click()
        return self

    def set_title(self, new_title: str) -> None:
        with allure.step(f"{self} enter new title: {new_title}"):
            log.info(f"{self} enter new title: {new_title}")
            edit_element = self.header_title
            self.clear_input(edit_element)
            edit_element.send_keys(new_title)
            self._change_title(new_title)
            time.sleep(1)

    def confirm_title(self):
        with allure.step(f"{self}: confirm new title"):
            log.info(f"{self}: confirm new title")
            self._button_confirm_title.click()
            time.sleep(3)
            _check_button_is_not_exist(lambda: self._button_confirm_title, 'confirm')
            if self.header_text != self.title:
                raise RuntimeError(f"{self}: wrong title")
        return self

    def cancel_title(self, old_title=None) -> None:
        ''' Editing widget title via clicking header: cancel changes with "Cancel" button '''
        with allure.step(f"{self}: cancel editing title"):
            log.info(f"{self}: cancel editing title")
            self._button_cancel_title.click()
            _check_button_is_not_exist(lambda: self._button_cancel_title, 'cancel')
            if old_title:
                self._change_title(old_title)
                time.sleep(3)
                if self.header_text != old_title:
                    raise RuntimeError(f"{self}: wrong title")
