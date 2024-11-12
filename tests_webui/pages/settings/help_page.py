import logging

from pages.navigation import BaseNavigationPage

log = logging.getLogger(__name__)


class HelpPage(BaseNavigationPage):
    path = '/help'

    def __init__(self, *args, **kwargs):
        super().__init__(title='Help', *args, **kwargs)

    @property
    def schema(self):
        schema = []
        for menu_entry in self.navigation:
            schema.append(menu_entry.title)
        return schema

    @property
    def content(self):
        content_element = self.get_object(self._x_content)
        return content_element.text
