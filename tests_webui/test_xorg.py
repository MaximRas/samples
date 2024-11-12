'''
Tests which are not possible to run in headless mode.
Someone has to run tests manually during regression
'''

# TODO: test for copying value of generated license (license server)

import re

import allure
import pytest
import pyperclip

from tools import config
from tools import join_url
from tools.steps import create_any_widget

from tests_webui.regression import check_hide_show_panel


@pytest.fixture(scope='function')
def teardown_clipboard():
    pyperclip.copy('')
    yield
    pyperclip.copy('')


@allure.epic('Frontend')
@allure.suite('Widgets')
@allure.title('Widget share -> link is in buffer after clicking "Copy" button')
@pytest.mark.usefixtures("teardown_delete_layouts")
@pytest.mark.usefixtures("teardown_clipboard")
def test_copy_value_dialog_share_widget(metapix):
    widget = create_any_widget(metapix.dashboard)

    with allure.step('Copy shared widget link with clicking "Copy" button'):
        widget.open_share_dialog().copy(delay=0)
        metapix.assert_tooltip('Link copied')
        link = pyperclip.paste()

    with allure.step(f'Check link from clipbaord: {link}'):
        assert re.findall('^' + join_url(config.web_url, r'/shared-widget/\d+/[a-z0-9\-]+$'), link)


@allure.epic('Frontend')
@allure.suite('Layouts')
@allure.title('Layout share -> link is in buffer after clicking "Copy" button')
@pytest.mark.usefixtures("teardown_delete_layouts")
@pytest.mark.usefixtures("teardown_clipboard")
def test_copy_value_dialog_share_layout(metapix):
    with allure.step('Copy shared layout link with clicking "Copy" button'):
        metapix.layout.open_share_dialog().copy(delay=0)
        metapix.assert_tooltip('Link copied')
        link = pyperclip.paste()

    with allure.step(f'Check link from clipbaord: {link}'):
        assert re.findall('^' + join_url(config.web_url, r'/shared-layout/\d+/[a-z0-9\-]+$'), link)


@allure.epic('Frontend')
@allure.suite('Profile')
@allure.title('Generate gateway token -> token is in buffer after clicking "Copy" button')
@pytest.mark.usefixtures("teardown_clipboard")
@pytest.mark.usefixtures('teardown_delete_tokens')
def test_copy_value_dialog_generate_gateway_token(metapix):
    with allure.step('Generate token and copy it'):
        tokens_page = metapix.open_settings(). \
            open_tokens()
        tokens_page. \
            open_add_token_dialog() .\
            set_value("New token"). \
            confirm()
        tokens_page.copy_token_dialog.copy()
        metapix.assert_tooltip('Token copied')
        token = pyperclip.paste()

    with allure.step('Check token from clipbaord'):
        assert re.findall(r'^[a-zA-Z_0-9\.\-]{204,205}$', token)


@allure.epic('Frontend')
@allure.suite('Device Tree')
@allure.title('Check hide/show left panel with cameras')
@pytest.mark.usefixtures('teardown_device_tree_show_cameras_panel')
def test_device_tree_hide_show_cameras_panel(metapix):
    device_tree = metapix.open_device_tree()
    check_hide_show_panel(
        device_tree.cameras_left_panel,
        hide_func=device_tree.hide_cameras,
        show_func=device_tree.show_cameras,
        refresh_func=metapix.refresh,
    )


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.title("[V2] It should be possible to hide/show left panel (when there is and no data)")
@pytest.mark.usefixtures('teardown_search_show_filters_panel')
def test_v2_search_hide_show_left_panel(metapix):
    results = metapix.search('face', ignore_no_data=True, fetch_more=False)

    check_hide_show_panel(
        results.filters_panel,
        hide_func=results.hide_filters_panel,
        show_func=results.show_filters_panel,
        refresh_func=metapix.refresh,
    )


@allure.epic("Frontend")
@allure.suite("Advanced Search")
@allure.tag("bug")
@allure.title('[v2] "Open left panel button" is enabled during search and in case of error')
@pytest.mark.usefixtures('teardown_delete_network_conditions')
@pytest.mark.usefixtures('teardown_search_show_filters_panel')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/1393')
@allure.link('https://gitlab.dev.metapixai.com/metapix-cloud/client/metapix-frontend-app/-/issues/975')
def test_v2_search_disabled_panel_button(metapix):
    search_panel = metapix.open_search_panel()
    metapix.set_network_conditions(download_throughput=1)

    with allure.step('Check "open left panel" button is enabled during search'):
        results = search_panel.get_results(wait_spinner_disappeared=False, ignore_no_data=True, fetch_more=False)
        results.hide_filters_panel()
        results.show_filters_panel()
        assert results.filters_panel.is_expanded()
        assert results.is_spinner_showing(x_root=results.x_root)  # self check
