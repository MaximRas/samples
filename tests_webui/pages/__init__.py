import allure

from pages.navigation import BaseContentTable
from pages.navigation import get_column
from tools import WebElement


class BaseTableRow:
    def __init__(self, element: WebElement, parent: object):
        self._element = element
        self._parent = parent

    def get_field_by_header(self, label: str) -> str:
        with allure.step('Try to get text from web element'):
            try:
                ix = self._parent.table_headers.index(label)
                element = get_column(self._element, ix)
                return element.text
            except ValueError as e:
                raise ValueError(f'Cannot find web element with name "{label}" \n Error: {e}')
