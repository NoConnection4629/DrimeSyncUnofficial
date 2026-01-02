import pytest
from unittest.mock import MagicMock, patch
import sys
if 'toga' not in sys.modules:
    sys.modules['toga'] = MagicMock()
import toga
from toga.style import Pack
from drimesyncunofficial.downloads_menu import DownloadsMenu
from drimesyncunofficial.uploads_menu import UploadsMenu
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'e2ee_enabled': False,
        'encryption_mode': 'no_enc',
        'api_key': 'test_key'
    }
    return app
def test_downloads_menu_show(mock_app):
    menu = DownloadsMenu(mock_app)
    with patch('toga.Window') as mock_window, \
         patch('toga.Box'), \
         patch('toga.Button'), \
         patch('toga.Label'), \
         patch('toga.Switch'), \
         patch('toga.Divider'):
        menu.show()
        mock_app.changer_ecran.assert_called_once()
import asyncio

def test_downloads_menu_dispatch_standard(mock_app):
    menu = DownloadsMenu(mock_app)
    menu.chk_mode = MagicMock(value=False)
    menu.window = MagicMock()
    with patch('drimesyncunofficial.downloads_workspace.WorkspaceDownloadManager') as mock_mgr:
        menu.open_ws_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
    with patch('drimesyncunofficial.downloads_manual.ManualDownloadManager') as mock_mgr:
        asyncio.run(menu.open_manual_dispatch(None))
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()

def test_downloads_menu_dispatch_e2ee(mock_app):
    menu = DownloadsMenu(mock_app)
    menu.chk_mode = MagicMock(value=True)
    menu.window = MagicMock()
    with patch('drimesyncunofficial.downloads_workspace_e2ee.WorkspaceDownloadE2EEManager') as mock_mgr:
        menu.open_ws_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
    with patch('drimesyncunofficial.downloads_manual_e2ee.ManualDownloadE2EEManager') as mock_mgr:
        asyncio.run(menu.open_manual_dispatch(None))
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
def test_uploads_menu_show(mock_app):
    menu = UploadsMenu(mock_app)
    with patch('toga.Window') as mock_window, \
         patch('toga.Box'), \
         patch('toga.Button'), \
         patch('toga.Label'), \
         patch('toga.Divider'):
        menu.show()
        mock_app.changer_ecran.assert_called_once()
from drimesyncunofficial.utils import MODE_NO_ENC, MODE_E2EE_STANDARD
def test_uploads_menu_dispatch_standard(mock_app):
    mock_app.config_data['encryption_mode'] = MODE_NO_ENC
    menu = UploadsMenu(mock_app)
    menu.window = MagicMock()
    with patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager') as mock_mgr:
        menu.open_mirror_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
    with patch('drimesyncunofficial.uploads_manual.ManualUploadManager') as mock_mgr:
        menu.open_manual_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
def test_uploads_menu_dispatch_e2ee(mock_app):
    mock_app.config_data['encryption_mode'] = MODE_E2EE_STANDARD
    menu = UploadsMenu(mock_app)
    menu.window = MagicMock()
    with patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager') as mock_mgr:
        menu.open_mirror_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
    with patch('drimesyncunofficial.uploads_manual_e2ee.ManualUploadE2EEManager') as mock_mgr:
        menu.open_manual_dispatch(None)
        mock_mgr.assert_called_with(mock_app)
        mock_mgr.return_value.show.assert_called_once()
if __name__ == "__main__":
    pytest.main([__file__])