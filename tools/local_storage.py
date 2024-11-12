import logging
from typing import Iterable

import allure

from tools.webdriver import CustomWebDriver

log = logging.getLogger(__name__)


class LocalStorage:
    def __init__(self, driver: CustomWebDriver):
        self._driver = driver

    def __str__(self):
        return "LocalStorage"

    def __len__(self):
        return self._driver.execute_script("return window.localStorage.length;")

    def items(self) -> Iterable[str]:
        return self._driver.execute_script(
            "var ls = window.localStorage, items = {}; "
            "for (var i = 0, k; i < ls.length; ++i) "
            "  items[k = ls.key(i)] = ls.getItem(k); "
            "return items; ")

    def keys(self) -> Iterable[str]:
        return self._driver.execute_script(
            "var ls = window.localStorage, keys = []; "
            "for (var i = 0; i < ls.length; ++i) "
            "  keys[i] = ls.key(i); "
            "return keys; ")

    def get(self, key: str) -> str:
        return self._driver.execute_script("return window.localStorage.getItem(arguments[0]);", key)

    def set(self, key: str, value: str):
        self._driver.execute_script("window.localStorage.setItem(arguments[0], arguments[1]);", key, value)

    def has(self, key: str) -> bool:
        return key in self.keys()

    def remove(self, key: str) -> None:
        with allure.step(f"{self}: remove key {key}"):
            log.info(f"  - remove key {key}")
            self._driver.execute_script("window.localStorage.removeItem(arguments[0]);", key)
            assert key not in self.keys()

    def clear(self) -> None:
        with allure.step(f"{self}: clear all"):
            log.info(f"{self}: clear all")
            self._driver.execute_script("window.localStorage.clear();")
            assert not self.keys()

    def __getitem__(self, key):
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key, value):
        self.set(key, value)

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return self.items().__iter__()


def clear_local_storage(
        local_storage: LocalStorage,
        description: str,
        exceptions: Iterable[str] = [],
) -> None:
    with allure.step(f'Clear Local Storage ({description}): except {exceptions}'):
        log.info(f'Clear Local Storage ({description}): except {exceptions}')
        for storage_key in local_storage.keys():
            if storage_key not in exceptions:
                local_storage.remove(storage_key)
