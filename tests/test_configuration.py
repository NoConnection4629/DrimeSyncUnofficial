import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import json
from drimesyncunofficial.configuration import ConfigManager, ExclusionEditor
class TestConfigManager:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.config_data = {
            'api_key': 'old_key',
            'workers': 5,
            'semaphores': 0,
            'debug_mode': False,
            'use_exclusions': True
        }
        app.config_path = "config.json"
        app.verify_api_startup = AsyncMock() 
        return app
    @pytest.fixture
    def config_manager(self, mock_app):
        with patch('toga.Window'), patch('toga.Box'), patch('toga.Label'), \
             patch('toga.Button'), patch('toga.TextInput'), patch('toga.NumberInput'), \
             patch('toga.Switch'), patch('toga.ScrollContainer'), patch('toga.Divider'):
            manager = ConfigManager(mock_app)
            manager.input_api = MagicMock()
            manager.input_api.value = "new_key"
            manager.input_workers = MagicMock()
            manager.input_workers.value = 10
            manager.input_semaphores = MagicMock()
            manager.input_semaphores.value = 2
            manager.chk_debug = MagicMock()
            manager.chk_debug.value = True
            manager.chk_exclusions = MagicMock()
            manager.chk_exclusions.value = False
            manager.window = MagicMock()
            manager.window.error_dialog = AsyncMock() 
            manager.window.close = MagicMock()
            return manager
    @pytest.mark.asyncio
    async def test_save_config_action(self, config_manager, mock_app):
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('drimesyncunofficial.configuration.set_secure_secret', return_value=True) as mock_set_secret:
            await config_manager.save_config_action(None)
            assert mock_app.config_data['api_key'] == "new_key"
            assert mock_app.config_data['workers'] == 10
            assert mock_app.config_data['semaphores'] == 2
            assert mock_app.config_data['debug_mode'] is True
            assert mock_app.config_data['use_exclusions'] is False
            mock_set_secret.assert_any_call("api_key", "new_key")
            mock_file.assert_called_with("config.json", 'w', encoding='utf-8')
            args, _ = mock_json_dump.call_args
            saved_dict = args[0]
            assert saved_dict['api_key'] == "" 
            assert saved_dict['workers'] == 10
            mock_app.verify_api_startup.assert_called_once()
            mock_app.retour_arriere.assert_called_once()
    def test_action_reset_key_ui(self, config_manager, mock_app):
        config_manager.show = MagicMock()
        with patch('drimesyncunofficial.configuration.set_secure_secret') as mock_set_secret:
            config_manager.action_reset_key_ui(None)
            
            assert mock_app.config_data['api_key'] == ""
            mock_app.retour_arriere.assert_called_once()
            config_manager.show.assert_called_once()
            mock_set_secret.assert_called_with("api_key", "")
class TestExclusionEditor:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.paths = MagicMock()
        return app
    @pytest.fixture
    def exclusion_editor(self, mock_app):
        with patch('toga.Window'), patch('toga.Box'), patch('toga.Label'), \
             patch('toga.Button'), patch('toga.MultilineTextInput'):
            editor = ExclusionEditor(mock_app)
            editor.txt_content = MagicMock()
            editor.txt_content.value = "*.test"
            editor.window = MagicMock()
            return editor
    def test_save_exclusion(self, exclusion_editor, mock_app):
        with patch('drimesyncunofficial.configuration.get_global_exclusion_path', return_value="exclude.txt"), \
             patch('builtins.open', mock_open()) as mock_file:
            exclusion_editor.save(None)
            mock_file.assert_called_with("exclude.txt", 'w', encoding='utf-8')
            mock_file().write.assert_called_with("*.test")
            mock_app.retour_arriere.assert_called_once()