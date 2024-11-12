from typing import Sequence

from pages.base_page import BasePage
from pages.pagination import Pagination


class LicenseServerBaseContentTable(BasePage):
    def __init__(self, x_root, *args, **kwargs):
        self.x_root = x_root
        super().__init__(*args, **kwargs)

    @property
    def _rows(self):
        return self.get_objects(self.x_root + "//tbody//tr")

    @property
    def pages(self):
        return Pagination(driver=self._driver, x_root=self.x_root)

    @property
    def table_name(self):
        header = self.get_desc_obj("//p[contains(@class, 'UIContentHeader')]", min_opacity=0.5)
        return header.get_attribute("textContent")

    @property
    def table_headers(self) -> Sequence[str]:
        headers = [header.text.strip() for header in self.get_objects(self.x_root + '//th')]
        return tuple(filter(lambda x: x, headers))

    @property
    def captions(self):
        captions = []
        for h6 in self.get_objects(self.x_root + '//h6'):
            captions.append(h6.text)
        return captions
