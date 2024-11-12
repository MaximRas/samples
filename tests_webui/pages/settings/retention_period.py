import logging
from pages.input_field import InputWithSelect

from pages.navigation import BaseContentTable


log = logging.getLogger(__name__)


class RetentionPeriodPage(BaseContentTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, title="Object Retention Period", **kwargs)

    @property
    def input_retention(self) -> InputWithSelect:
        return InputWithSelect(label="Retention Period", driver=self.driver, x_root=self.x_root)

    @property
    def period_value(self) -> int:
        return int(self.input_retention.value)
