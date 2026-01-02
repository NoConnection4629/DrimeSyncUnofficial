import sys
import importlib
from unittest.mock import MagicMock, patch, ANY
import pytest
import os
class MockBox:
    def __init__(self, style=None, **kwargs):
        self.style = style
        self.children = []
    def add(self, widget):
        self.children.append(widget)
@pytest.fixture(scope="function")
def mock_browser_env():
    """
    Sets up a mocked Toga environment in sys.modules,
    then reloads the browsers module to use the mock.
    Cleans up afterwards.
    """
    mock_toga = MagicMock()
    mock_toga.Box = MockBox
    mock_pack = MagicMock()
    mock_toga.style.Pack = mock_pack
    mock_style = MagicMock()
    mock_style.pack = MagicMock()
    mock_style.pack.COLUMN = 'column'
    mock_style.pack.ROW = 'row'
    mock_toga.style = mock_style
    modules_to_patch = {
        'toga': mock_toga,
        'toga.style': mock_style,
        'toga.style.pack': mock_style.pack
    }
    with patch.dict(sys.modules, modules_to_patch):
        from drimesyncunofficial import browsers
        importlib.reload(browsers)
        yield browsers.AndroidFileBrowser
    if 'drimesyncunofficial.browsers' in sys.modules:
        from drimesyncunofficial import browsers
        try:
            importlib.reload(browsers)
        except ImportError:
            pass
class TestAndroidFileBrowser:
    def _create_browser(self, AndroidFileBrowserClass, is_folder_mode=False):
        app = MagicMock()
        app.main_window = MagicMock()
        app.is_mobile = True
        with patch('drimesyncunofficial.browsers.os.scandir') as mock_scandir:
             mock_scandir.return_value.__enter__.return_value = []
             browser = AndroidFileBrowserClass(app, lambda x: None, initial_path="/test/path", folder_selection_mode=is_folder_mode)
        return browser
    def test_initialization(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser)
        assert browser.current_path == "/test/path"
        assert browser.folder_selection_mode is False
        assert browser.lbl_path.text.startswith("📂 path")
    def test_initialization_folder_mode(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser, is_folder_mode=True)
        assert browser.folder_selection_mode is True
        assert len(browser.children) > 0
    def test_go_up(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser)
        browser.current_path = "/test/path/subdir"
        with patch('drimesyncunofficial.browsers.os.scandir') as mock_scandir:
             mock_scandir.return_value.__enter__.return_value = []
             browser.go_up(None)
        import os
        expected_parent = os.path.dirname("/test/path/subdir")
        assert browser.current_path == expected_parent
    def test_on_row_select_file_mode(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser)
        mock_callback = MagicMock()
        browser.on_select_callback = mock_callback
        row_mock = MagicMock()
        row_mock.is_dir = False
        row_mock.path = "/test/path/file.txt"
        browser.on_row_select(None, row=row_mock)
        mock_callback.assert_called_once_with(["/test/path/file.txt"])
    def test_on_row_select_folder_mode(self, mock_browser_env):
         AndroidFileBrowser = mock_browser_env
         browser = self._create_browser(AndroidFileBrowser, is_folder_mode=True)
         mock_callback = MagicMock()
         browser.on_select_callback = mock_callback
         row_mock = MagicMock()
         row_mock.is_dir = False
         row_mock.path = "/test/path/file.txt"
         browser.on_row_select(None, row=row_mock)
         mock_callback.assert_not_called()
    def test_on_row_select_directory(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser)
        row_mock = MagicMock()
        row_mock.is_dir = True
        row_mock.path = "/test/path/newdir"
        with patch('drimesyncunofficial.browsers.os.scandir') as mock_scandir:
             mock_scandir.return_value.__enter__.return_value = []
             browser.on_row_select(None, row=row_mock)
        assert browser.current_path == "/test/path/newdir"
    def test_row_attribute_fallback(self, mock_browser_env):
        AndroidFileBrowser = mock_browser_env
        browser = self._create_browser(AndroidFileBrowser)
        mock_callback = MagicMock()
        browser.on_select_callback = mock_callback
        class SimpleRow:
            pass
        row = SimpleRow()
        row.is_dir = False
        row.path = "/simple/path.txt"
        browser.on_row_select(None, row=row)
        mock_callback.assert_called_with(["/simple/path.txt"])