import bs4
import requests

from tools.types import UrlType


class UnableGetAppVersion(Exception):
    pass


class AppVersion:
    def __init__(self, version_str):
        self._version_str = version_str

    def __int__(self):
        parts = [int(part) for part in self._version_str.split(".")]
        number = parts[0] * 1e9 + parts[1] * 1e7 + parts[2]*1e4
        if len(parts) > 3:
            number += parts[3]
        return int(number)

    def __gt__(self, o):
        if o is None:
            raise ValueError('Right value is None')
        return int(self) > int(o)

    def __eq__(self, o):
        return int(self) == int(o)

    def __str__(self):
        return self._version_str

    def __repr__(self):
        return f"Version {self._version_str} ({int(self)})"


def get_app_version(url: UrlType) -> AppVersion:
    parser = bs4.BeautifulSoup(requests.get(url).text, "lxml")
    try:
        version = parser.find("meta", {"name": "version"})["content"]  # type: ignore[reportOptionalSubscript]
    except TypeError as exc:
        raise UnableGetAppVersion from exc
    return AppVersion(version)
