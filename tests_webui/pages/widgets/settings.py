import logging

import allure
from seleniumwire.request import Request

import consts

from tools.layouts import get_layouts
from tools.layouts import get_layout

from pages.button import Button
from pages.widgets.base_settings import BaseWidgetSettings

log = logging.getLogger(__name__)


class WidgetSettings(BaseWidgetSettings):
    def __init__(self, parent, *args, **kwargs):
        self._parent = parent  # widget
        super().__init__(*args, title="Widget settings", **kwargs)

    @property
    def button_ok(self):
        return Button(driver=self._driver, label="Change widget", x_root=self.x_root)

    def apply(self, *args, **kwargs):
        url_to_intercept = '/object-manager/v2/search/' if self._parent.type == consts.WIDGET_LIVE_FEED else '/chartilla/chart'
        interceptor_data = {'request_has_been_aborted': False, 'counter': 0, 'raise_exception': None}

        # FYI: https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1541#note_80029
        drop_second_req = False
        raise_if_wrong_count = False

        def request_interceptor(request: Request):
            # FYI https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1555
            # FYI 0.48.3 is still affected by this bug https://metapix-workspace.slack.com/archives/C03L82QCEJC/p1727705297519099
            if url_to_intercept in request.path:
                interceptor_data['counter'] += 1

                if interceptor_data['counter'] > 1:
                    if raise_if_wrong_count:
                        interceptor_data['raise_exception'] = RuntimeError(f'Too much requests: {interceptor_data["counter"]}')
                    log.error(f'Too much requests: {interceptor_data["counter"]}')

                if drop_second_req:
                    if interceptor_data['request_has_been_aborted'] is True:
                        log.info(f'allow {request} with body {request.body}')
                    else:
                        log.warning(f'abort {request} with body: {request.body}')
                        request.abort()
                        interceptor_data['request_has_been_aborted'] = True

        with allure.step('Apply widget settings'):
            log.info(f'Apply widget settings: {self}')
            if self._parent.title != self.input_title.value:
                log.info(f"{self} title has been changed: {self._parent.title} -> {self.input_title.value}")
                self._parent._change_title(self.input_title.value)

            default_layout = get_layout(
                self.driver.client,
                next(
                    filter(
                        lambda layout: layout.default is True,
                        get_layouts(self.driver.client),
                    )
                )
            )
            number_of_widgets = len(default_layout.grid)
            if number_of_widgets > 1:
                log.warning(f'{self}: do not install request interceptor. {number_of_widgets=}')
            if number_of_widgets == 1:
                self.driver.request_interceptor = request_interceptor

            try:
                super().apply(
                    *args,
                    clickhouse_lag=False,
                    delay=kwargs.pop('delay', 10),
                    **kwargs,
                )
            finally:
                del self.driver.request_interceptor
                if interceptor_data['raise_exception']:
                    raise interceptor_data['raise_exception']
