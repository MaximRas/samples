from typing import Any
from typing import Mapping
from typing import Optional
from typing import Sequence
import logging
import time

import allure
from typing_extensions import Self

import consts
from tools.ico_button import get_ico_button
from tools.ico_button import IcoButton
from tools.types import IcoType
from tools.types import XPathType
from tools.webdriver import WebElement

from pages.ico_dialog import IcoDialog
from pages.button import Button
from pages.confirm_dialog import ConfirmDialog
from pages.dialog import Dialog
from pages.dropdown import Select
from pages.input_field import Input_v0_48_4
from pages.navigation import BaseContentTable
from pages.navigation import ICO_PENCIL
from pages.navigation import ICO_TRASH_CAN
from pages.navigation import get_button
from pages.navigation import get_column
from pages.search.age_slider import AgeSlider
from pages.search.base_filters import DropdownInputFilters
from pages.widgets.base_settings import BaseWidgetSettings

log = logging.getLogger(__name__)

ICO_BACK_ARROW = IcoType('M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z')
CLUSTER_NAME = 'Cluster Name'
ALL_CLUSTERS = 'All clusters'


class EditWatchListDialog(ConfirmDialog):
    def __init__(self, watchlist_name, *args, **kwargs):
        self._watchlist_name = watchlist_name
        super().__init__(
            title=f'Edit Watch List "{self._watchlist_name}"',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            *args, **kwargs,
        )

    @property
    def input_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(driver=self.driver, label=consts.FILTER_WATCHLIST_NAME, x_root=self.x_root)

    @property
    def ico_close(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_CLOSE1, button_tag=XPathType('span'))


class WatchListDeletedDialog(Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Success',
            is_mui=False,
            has_close_icon=True,
            ico_close=consts.ICO_CLOSE1,
            *args, **kwargs,
        )


class DeleteWatchListDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Delete Watch List',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            confirm_label='Submit',
            *args, **kwargs,
        )

    @property
    def ico_close(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_CLOSE1, button_tag=XPathType('span'))

    def confirm(self, *args, **kwargs) -> WatchListDeletedDialog:
        super().confirm(*args, **kwargs)
        return WatchListDeletedDialog(driver=self.driver)


class DeleteFilterDialog(ConfirmDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Delete Filter',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            confirm_label='Submit',
            *args, **kwargs,
        )

    @property
    def ico_close(self) -> IcoButton:
        return get_ico_button(self, consts.ICO_CLOSE1, button_tag=XPathType('span'))

    def confirm(self, *args, **kwargs) -> WatchListDeletedDialog:
        super().confirm(*args, **kwargs)
        success_dialog = WatchListDeletedDialog(driver=self.driver)
        return success_dialog


class WatchListFilterRow:
    def __init__(self, element, parent):
        self._element = element
        self._parent = parent

    def __str__(self):
        return f'Filter "{self._element.text}"'

    @property
    def cluster_name(self) -> str:
        assert CLUSTER_NAME in self._parent.table_headers
        ix = self._parent.table_headers.index(CLUSTER_NAME)
        return get_column(self._element, ix).text

    @property
    def _button_edit(self) -> WebElement:
        return get_button(self._element, ICO_PENCIL)

    @property
    def _button_delete(self) -> WebElement:
        return get_button(self._element, ICO_TRASH_CAN)

    def open_delete_dialog(self) -> DeleteFilterDialog:
        with allure.step(f'Open "delete dialog" for {self}'):
            log.info(f'Open "delete dialog" for {self}')
            self._button_delete.click()
            return DeleteFilterDialog(driver=self._parent.driver)

    def delete(self) -> None:
        with allure.step(f'Delete {self}'):
            log.info(f'Delete {self}')
            delete_dialog = self.open_delete_dialog()
            success_dialog = delete_dialog.confirm()
            success_dialog.close()

    def open_edit_dialog(self) -> ConfirmDialog:   # TODO: fix return type
        with allure.step(f'Open edit dialog for {self}'):
            log.info(f'Open edit dialog for {self}')
            self._button_edit.click()
            return EditFilterForWatchlistDialog(driver=self._parent.driver)

    def edit(self, filters: Mapping[str, Any]) -> None:
        '''
        FYI (pop-ups after editing):
          0.48 https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1369 (check out all the comments)
          0.47 https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1368
        '''
        with allure.step(f'Edit filter for {self.cluster_name}'):
            log.info(f'Edit filter for {self.cluster_name}')
            edit_dialog = self.open_edit_dialog()
            edit_dialog.set_filters(filters)
            edit_dialog.confirm()
            time.sleep(1)  # wait table is updated


class WatchListFiltersTable(BaseContentTable):
    def __init__(self, watchlist_name, *args, **kwargs):
        self._watchlist_name = watchlist_name
        super().__init__(title=f'Filters in {self._watchlist_name}', *args, **kwargs)

    def refresh(self) -> Self:
        return super().refresh(watchlist_name=self._watchlist_name)

    @property
    def _filters(self) -> Sequence[WatchListFilterRow]:
        return [WatchListFilterRow(row, self) for row in self._rows]

    @property
    def button_add(self) -> Button:
        return Button(
            driver=self.driver,
            x_root=self.x_root,
            label='Add Filter',
            is_mui=False,
        )

    @property
    def schema(self) -> Sequence[dict] | str:
        base_to_headers = {
            'face': (CLUSTER_NAME, 'Age', 'Gender'),
            'vehicle': ('Vehicle Type', 'Vehicle License Plate'),
        }

        if not self._rows:
            return IcoDialog(driver=self.driver, x_root=self.x_root).text

        if base_to_headers['face'] == self.table_headers:
            base = 'face'
        elif base_to_headers['vehicle'] == self.table_headers:
            base = 'vehicle'
        else:
            raise RuntimeError('Unexpected behavior: unable to determine base (mind the table headers)')

        _schema = []
        for row in self._rows:
            _schema.append({})
            for ix, header in enumerate(base_to_headers[base]):
                _schema[-1][header] = get_column(row, ix).text

        return sorted(_schema, key=lambda x: tuple(x.values()))

    def get(self, ix=None, cluster_name=None) -> WatchListFilterRow:
        ''' Filter entities don't have an uniq column... '''
        if ix is not None:
            return self._filters[ix]
        if cluster_name is not None:
            for predicates in self._filters:
                if predicates.cluster_name == cluster_name:
                    return predicates
            else:
                raise RuntimeError(f'No filter with {cluster_name=}')
        raise RuntimeError

    def add(self, filters):
        with allure.step(f'Add new filter for {self}: filters'):
            log.info(f'Add new filter for {self}: filters')
            self.button_add.click()
            add_dialog = AddFilterForWatchlistDialog(
                watchlist_name=self._watchlist_name,
                driver=self.driver,
            )
            add_dialog.set_filters(filters)
            add_dialog.confirm()


class WatchListRow:
    def __init__(self, element, parent):
        self._element = element
        self._parent = parent

    def __str__(self) -> str:
        return f'WatchList {self.name}'

    @property
    def name(self) -> str:
        return get_column(self._element, 0).text

    @property
    def button_edit(self) -> WebElement:
        return get_button(self._element, ICO_PENCIL)

    @property
    def button_delete(self) -> WebElement:
        return get_button(self._element, ICO_TRASH_CAN)

    @property
    def button_open(self) -> IcoButton:
        return get_ico_button(
            self._element,
            ico=consts.ICO_RIGHT_ARROW,
            button_tag=".//span",
        )

    def open_delete_dialog(self) -> DeleteWatchListDialog:
        with allure.step(f'Open delete dialog for {self}'):
            log.info(f'Open delete dialog for {self}')
            self.button_delete.click()
            delete_dialog = DeleteWatchListDialog(driver=self._parent.driver)
            return delete_dialog

    def open_filters(self) -> WatchListFiltersTable:
        with allure.step(f'Open filter for {self}'):
            log.info(f'Open filter for {self}')
            watchlist_name = self.name  # save name before cliking
            self.button_open.click()
            self._parent.wait_spinner_disappeared()
            return WatchListFiltersTable(
                watchlist_name=watchlist_name,
                driver=self._parent.driver,
            )

    def edit(self, name):
        '''
        FYI (pop-ups after editing):
          0.48 https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1369 (check out all the comments)
          0.47 https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1368
        '''
        with allure.step(f'Edit {self}: change name -> {name}'):
            self.button_edit.click()
            edit_dialog = EditWatchListDialog(
                watchlist_name=self.name,
                driver=self._parent.driver,
            )
            edit_dialog.input_name.type_text(name, clear_with_keyboard=True)
            edit_dialog.confirm()
            time.sleep(1)  # wait table is updated


class WatchListAddedDialog(Dialog):
    def __init__(self, name, *args, **kwargs):
        self._name = name
        super().__init__(
            title='Success',
            is_mui=False,
            has_close_icon=True,
            ico_close=consts.ICO_CLOSE1,
            *args, **kwargs,
        )

    def close(self) -> WatchListFiltersTable:
        super().close()
        table_with_filters = WatchListFiltersTable(watchlist_name=self._name, driver=self.driver)
        return table_with_filters


class AddFilterForWatchlistDialog(ConfirmDialog, DropdownInputFilters):
    def __init__(self, watchlist_name, *args, **kwargs):
        self._watchlist_name = watchlist_name
        super().__init__(
            *args,
            title=f'Add Filter for "{self._watchlist_name}"',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            **kwargs,
        )

    def set_filters(self, *args, **kwargs):
        BaseWidgetSettings.set_filters(self, *args, **kwargs)

    def confirm(self, *args, **kwargs) -> WatchListAddedDialog:
        super().confirm(wait_disappeared=False, *args, **kwargs)
        result_dialog = WatchListAddedDialog(name=self._watchlist_name, driver=self.driver)
        self.wait_disappeared()
        return result_dialog


class EditFilterForWatchlistDialog(AddFilterForWatchlistDialog):
    def __init__(self, *args, **kwargs):
        ConfirmDialog.__init__(
            self,
            *args,
            title='Edit Filter',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            **kwargs,
        )

    def confirm(self, *args, **kwargs):
        ConfirmDialog.confirm(
            self,
            wait_disappeared=kwargs.pop('wait_disappeared', True),
            *args, **kwargs,
        )


class AddWatchListDialog(ConfirmDialog, DropdownInputFilters):
    def __init__(self, *args, **kwargs):
        ConfirmDialog.__init__(
            self, *args,
            title='Add Watch List',
            is_mui=False,
            is_mui_confirm_button=False,
            is_mui_cancel_button=False,
            **kwargs,
        )
        self._watchlist_name = None

    @property
    def _input_name(self) -> Input_v0_48_4:
        return Input_v0_48_4(
            driver=self.driver,
            label=consts.FILTER_WATCHLIST_NAME,
            x_root=self.x_root,
        )

    @property
    def dropdown_base(self) -> Select:
        return Select(label='Object Type', driver=self.driver, x_root=self.x_root)

    def set_name(self, name: str):
        with allure.step(f'{self} set {name=}'):
            log.info(f'{self} set {name=}')
            self._input_name.type_text(name)
            self._watchlist_name = name

    @property
    def age_slider(self) -> AgeSlider:
        return AgeSlider(driver=self.driver, x_root=self.x_root)

    def confirm(self, *args, **kwargs) -> Optional[WatchListAddedDialog]:
        wait_disappeared = kwargs.pop('wait_disappeared', True)
        super().confirm(
            wait_disappeared=wait_disappeared,
            *args, **kwargs)
        if wait_disappeared:
            result_dialog = WatchListAddedDialog(name=self._watchlist_name, driver=self.driver)
            self.wait_disappeared()
            return result_dialog

    def set_filters(self, *args, **kwargs):
        BaseWidgetSettings.set_filters(self, *args, **kwargs)


class WatchListsTable(BaseContentTable):
    def __init__(self, *args, **kwargs):
        super().__init__(
            title='Watch Lists',
            *args, **kwargs,
        )

    @property
    def _button_add_in_header(self) -> Button:
        return Button(
            driver=self.driver,
            x_root=self.x_root,
            label='Add Watch List',
            is_mui=False,
        )

    @property
    def _button_add_in_body(self) -> Button:
        return Button(
            driver=self.driver,
            x_root=self.x_root,
            label='Add Watch List',
            is_mui=False,
        )

    @property
    def _button_add(self) -> Button:
        if not self._rows:
            return self._button_add_in_body
        return self._button_add_in_header

    def open_add_dialog(self) -> AddWatchListDialog:
        self._button_add.click()
        return AddWatchListDialog(driver=self.driver)

    @property
    def schema(self) -> Sequence[dict] | str:
        _schema = []
        for row in self._rows:
            _schema.append({})
            for ix, header in enumerate(self.table_headers):
                _schema[-1][header] = get_column(row, ix).text
        if not _schema:
            return IcoDialog(driver=self.driver, x_root=self.x_root).text
        return _schema

    def get(self, name) -> WatchListRow:
        for row in self._rows:
            watchlist = WatchListRow(row, self)
            if watchlist.name == name:
                return watchlist
        else:
            raise RuntimeError(f'There is no watchlist with {name=}')
