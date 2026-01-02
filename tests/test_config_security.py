import pytest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import json
import sys
import asyncio
try:
    import toga
except ImportError:
    toga = MagicMock()
    sys.modules['toga'] = toga
    toga.style.pack = MagicMock()
    toga.style.Pack = MagicMock()
from drimesyncunofficial.configuration import ConfigManager
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'old_key',
        'e2ee_password': 'old_pass',
        'workers': 5,
        'semaphores': 0,
        'debug_mode': False,
        'use_exclusions': True
    }
    app.config_path = "dummy_config.json"
    app.paths = MagicMock()
    app.verify_api_startup = AsyncMock()
    return app
def test_save_config_desktop_clears_secrets(mock_app):
    """Verify that on Desktop (Windows), secrets are cleared from JSON."""
    async def _run_test():
        with patch('toga.platform.current_platform', 'windows'), \
             patch('drimesyncunofficial.configuration.set_secure_secret') as mock_set_secret, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:
            manager = ConfigManager(mock_app)
            manager.window = MagicMock()
            manager.window.error_dialog = AsyncMock()
            manager.input_api = MagicMock()
            manager.input_api.value = "new_api_key"
            manager.input_workers = MagicMock()
            manager.input_workers.value = 10
            manager.input_semaphores = MagicMock()
            manager.input_semaphores.value = 2
            manager.chk_debug = MagicMock()
            manager.chk_debug.value = True
            manager.chk_exclusions = MagicMock()
            manager.chk_exclusions.value = False
            mock_app.config_data['e2ee_password'] = "new_secret_pass"
            await manager.save_config_action(None)
            mock_set_secret.assert_any_call("api_key", "new_api_key")
            args, _ = mock_json_dump.call_args
            saved_json = args[0]
            assert saved_json['api_key'] == ""
            assert saved_json['e2ee_password'] == ""
            assert saved_json['workers'] == 10
    asyncio.run(_run_test())
def test_save_config_android_keeps_secrets(mock_app):
    """Verify that on Android, secrets are KEPT in JSON."""
    async def _run_test():
        with patch('toga.platform.current_platform', 'android'):
             manager = ConfigManager(mock_app)
             manager.window = MagicMock()
             manager.window.error_dialog = AsyncMock()
             manager.input_api = MagicMock()
             manager.input_api.value = "new_api_key"
             manager.input_workers = MagicMock()
             manager.input_workers.value = 10
             manager.input_semaphores = MagicMock()
             manager.input_semaphores.value = 2
             manager.chk_debug = MagicMock()
             manager.chk_debug.value = True
             manager.chk_exclusions = MagicMock()
             manager.chk_exclusions.value = False
             pass 
        with patch('drimesyncunofficial.configuration.toga.platform.current_platform', 'android'), \
             patch('drimesyncunofficial.configuration.set_secure_secret') as mock_set_secret, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:
            manager = ConfigManager(mock_app)
            manager.window = MagicMock()
            manager.window.error_dialog = AsyncMock()
            manager.input_api = MagicMock()
            manager.input_api.value = "new_api_key"
            manager.input_workers = MagicMock()
            manager.input_workers.value = 10
            manager.input_semaphores = MagicMock()
            manager.input_semaphores.value = 2
            manager.chk_debug = MagicMock()
            manager.chk_debug.value = True
            manager.chk_exclusions = MagicMock()
            manager.chk_exclusions.value = False
            mock_app.config_data['e2ee_password'] = "new_secret_pass"
            await manager.save_config_action(None)
            args, _ = mock_json_dump.call_args
            saved_json = args[0]
            assert saved_json['api_key'] == "new_api_key"
            assert saved_json['e2ee_password'] == "new_secret_pass"
    asyncio.run(_run_test())