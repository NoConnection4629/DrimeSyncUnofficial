import pytest
from unittest.mock import MagicMock, patch, mock_open
import json
import sys
from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager
try:
    import toga
except ImportError:
    toga = MagicMock()
    sys.modules['toga'] = toga
    toga.style.pack = MagicMock()
    toga.style.Pack = MagicMock()
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'secret_api_key',
        'e2ee_password': 'secret_password',
        'workspace_e2ee_id': '0',
        'folder_e2ee_path': '/tmp/test'
    }
    app.config_path = "dummy_config.json"
    app.paths = MagicMock()
    return app
def test_mirror_save_config_desktop_clears_secrets(mock_app):
    """Verify that _save_config_file in MirrorManager clears secrets on Desktop."""
    with patch('toga.platform.current_platform', 'windows'), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('json.dump') as mock_json_dump:
        manager = MirrorUploadE2EEManager(mock_app)
        manager.selection_mirror_ws = MagicMock()
        manager.selection_mirror_ws.value = "Test (ID: 123)"
        manager._save_config_file()
        args, _ = mock_json_dump.call_args
        saved_json = args[0]
        assert saved_json['api_key'] == "", "API Key should be cleared on Desktop"
        assert saved_json['e2ee_password'] == "", "E2EE Password should be cleared on Desktop"
        assert saved_json['workspace_e2ee_id'] == "123"
def test_mirror_save_config_android_keeps_secrets(mock_app):
    """Verify that _save_config_file in MirrorManager keeps secrets on Android."""
    with patch('toga.platform.current_platform', 'android'), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('json.dump') as mock_json_dump:
        manager = MirrorUploadE2EEManager(mock_app)
        manager.selection_mirror_ws = MagicMock()
        manager.selection_mirror_ws.value = "Test (ID: 123)"
        manager._save_config_file()
        args, _ = mock_json_dump.call_args
        saved_json = args[0]
        assert saved_json['api_key'] == "secret_api_key"
        assert saved_json['e2ee_password'] == "secret_password"
        assert saved_json['workspace_e2ee_id'] == "123"