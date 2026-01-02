import pytest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import json
import sys
import os
sys.path.insert(0, os.path.abspath("src"))
try:
    import toga
except ImportError:
    toga = MagicMock()
    sys.modules['toga'] = toga
    sys.modules['toga.style'] = MagicMock()
    sys.modules['toga.style.pack'] = MagicMock()
    pack_mock = MagicMock()
    sys.modules['toga.style'].Pack = pack_mock
    sys.modules['toga.style.pack'].COLUMN = 'COLUMN'
    sys.modules['toga.style.pack'].ROW = 'ROW'
    sys.modules['toga.style.pack'].BOLD = 'BOLD'
    sys.modules['toga.style.pack'].CENTER = 'CENTER'
try:
    import drimesyncunofficial.security
    print(f"DEBUG: drimesyncunofficial.security loaded from: {drimesyncunofficial.security.__file__}")
except Exception as e:
    print(f"DEBUG: Could not import drimesyncunofficial.security: {e}")
from drimesyncunofficial.security import SecurityManager
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'secret_api_key',
        'e2ee_password': 'secret_password',
        'encryption_mode': 'standard',
        '2fa_secret': 'secret_2fa'
    }
    app.config_path = "dummy_config.json"
    app.paths = MagicMock()
    app.main_window = MagicMock()
    app.main_window.dialog = AsyncMock()
    return app
def test_security_save_clears_secrets_on_desktop(mock_app):
    """Verify SecurityManager.action_save clears secrets on Desktop."""
    async def _run_test():
        with patch('toga.platform.current_platform', 'windows'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('drimesyncunofficial.security.set_secure_secret') as mock_set_secret:
            manager = SecurityManager(mock_app)
            manager.window = MagicMock()
            manager.window.dialog = AsyncMock()
            manager.window.close = MagicMock()
            manager.switch_2fa = MagicMock()
            manager.switch_2fa.value = False
            manager.current_mode = 'standard'
            manager.current_password = 'new_password'
            manager.secret_2fa = ''
            await manager.action_save(None)
            mock_set_secret.assert_any_call("e2ee_password", "new_password")
            args, _ = mock_json_dump.call_args
            saved_json = args[0]
            assert saved_json['api_key'] == ""
            assert saved_json['e2ee_password'] == ""
            assert saved_json['2fa_secret'] == ""
    import asyncio
    asyncio.run(_run_test())
def test_security_save_clears_2fa_secret_on_desktop(mock_app):
    """Verify SecurityManager clears 2fa_secret even if 2FA is active."""
    async def _run_test():
        with patch('toga.platform.current_platform', 'windows'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('drimesyncunofficial.security.set_secure_secret') as mock_set_secret:
            manager = SecurityManager(mock_app)
            manager.window = MagicMock()
            manager.window.dialog = AsyncMock()
            manager.window.close = MagicMock()
            manager.switch_2fa = MagicMock()
            manager.switch_2fa.value = True
            manager.secret_2fa = 'MY_SECRET_2FA_CODE'
            manager.current_mode = 'standard'
            manager.current_password = 'pass'
            await manager.action_save(None)
            mock_set_secret.assert_any_call("2fa_secret", "MY_SECRET_2FA_CODE")
            args, _ = mock_json_dump.call_args
            saved_json = args[0]
            assert saved_json['2fa_secret'] == ""
    import asyncio
    asyncio.run(_run_test())
def test_mirror_standard_save_clears_secrets_on_desktop(mock_app):
    """Verify MirrorUploadManager._save_config_file clears secrets on Desktop."""
    with patch('toga.platform.current_platform', 'windows'), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('json.dump') as mock_json_dump:
        manager = MirrorUploadManager(mock_app)
        manager.selection_mirror_ws = MagicMock()
        manager.selection_mirror_ws.value = "Test (ID: 123)"
        mock_app.config_data['workspace_standard_id'] = "123"
        mock_app.config_data['2fa_secret'] = "SECRET_SHOULD_BE_GONE"
        manager._save_config_file()
        args, _ = mock_json_dump.call_args
        saved_json = args[0]
        assert saved_json['api_key'] == ""
        assert saved_json['e2ee_password'] == ""
        assert saved_json['2fa_secret'] == ""
        assert saved_json['workspace_standard_id'] == "123"
if __name__ == "__main__":
    app = MagicMock()
    app.config_data = {
        'api_key': 'secret_api_key',
        'e2ee_password': 'secret_password',
        'encryption_mode': 'standard',
        '2fa_secret': 'secret_2fa'
    }
    app.config_path = "dummy_config.json"
    app.paths = MagicMock()
    app.main_window = MagicMock()
    app.main_window.dialog = AsyncMock()
    print("Running test_security_save_clears_secrets_on_desktop...")
    test_security_save_clears_secrets_on_desktop(app)
    print("PASS")
    print("Running test_mirror_standard_save_clears_secrets_on_desktop...")
    test_mirror_standard_save_clears_secrets_on_desktop(app)
    print("PASS")