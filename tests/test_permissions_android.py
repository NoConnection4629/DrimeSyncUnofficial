import pytest
from unittest.mock import MagicMock, patch, Mock
import sys

# Mocking android modules before they are imported by the code
sys.modules['android'] = MagicMock()
sys.modules['android.content'] = MagicMock()
sys.modules['android.net'] = MagicMock()
sys.modules['android.provider'] = MagicMock()
sys.modules['android.os'] = MagicMock()

from drimesyncunofficial.configuration import ConfigManager

class TestAndroidPermissions:
    
    @pytest.fixture
    def mock_android_modules(self):
        """Creates mocks for android modules and returns them"""
        mock_android = MagicMock()
        mock_intent = MagicMock()
        mock_uri = MagicMock()
        mock_settings = MagicMock()
        mock_build = MagicMock()
        mock_env = MagicMock()
        
        # Setup structure
        mock_intent.setData = MagicMock()
        
        modules = {
            'android': mock_android,
            'android.content': MagicMock(),
            'android.net': MagicMock(),
            'android.provider': MagicMock(),
            'android.os': MagicMock(),
        }
        
        # Assign attributes to the module mocks
        modules['android.content'].Intent = MagicMock(return_value=mock_intent)
        modules['android.net'].Uri = mock_uri
        modules['android.provider'].Settings = mock_settings
        modules['android.os'].Build = mock_build
        modules['android.os'].Environment = mock_env
        
        return modules, mock_intent, mock_uri, mock_settings, mock_build, mock_env

    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.main_window = MagicMock()
        app._impl = MagicMock()
        app._impl.native = MagicMock()
        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        return ConfigManager(mock_app)

    def test_permission_granted_already(self, config_manager, mock_app, mock_android_modules):
        modules, _, _, _, mock_build, mock_env = mock_android_modules
        
        with patch.dict(sys.modules, modules), \
             patch('toga.platform.current_platform', 'android'):
            
            # Setup
            mock_build.VERSION.SDK_INT = 30
            mock_env.isExternalStorageManager.return_value = True

            # Action
            config_manager.action_demander_permissions(None)

            # Assert
            mock_env.isExternalStorageManager.assert_called_once()
            mock_app.main_window.info_dialog.assert_called_with("C'est tout bon !", "L'accès à tous les fichiers est déjà activé. ✅")
            mock_app._impl.native.startActivity.assert_not_called()

    def test_permission_request_direct_success(self, config_manager, mock_app, mock_android_modules):
        modules, mock_intent_inst, mock_uri, mock_settings, mock_build, mock_env = mock_android_modules
        
        with patch.dict(sys.modules, modules), \
             patch('toga.platform.current_platform', 'android'):
            
            mock_build.VERSION.SDK_INT = 30
            mock_env.isExternalStorageManager.return_value = False
            mock_settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION = "ACTION_SPECIFIC"
            
            # Mock getPackageName via the activity context
            modules['android'].app.Activity.mActivity.getPackageName.return_value = "com.noconnection4629.drimesyncunofficial"

            config_manager.action_demander_permissions(None)
            
            mock_uri.parse.assert_called_with("package:com.noconnection4629.drimesyncunofficial")
            # Verify Intent was instantiated with specific action
            modules['android.content'].Intent.assert_any_call("ACTION_SPECIFIC")
            mock_app._impl.native.startActivity.assert_called()

    def test_permission_request_fallback(self, config_manager, mock_app, mock_android_modules):
        modules, mock_intent_inst, mock_uri, mock_settings, mock_build, mock_env = mock_android_modules
        
        with patch.dict(sys.modules, modules), \
             patch('toga.platform.current_platform', 'android'):
            
            mock_build.VERSION.SDK_INT = 30
            mock_env.isExternalStorageManager.return_value = False
            mock_settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION = "ACTION_SPECIFIC"
            mock_settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION = "ACTION_GENERIC"
            
            # Simulate crash on Uri.parse
            mock_uri.parse.side_effect = Exception("Fail")
            
            config_manager.action_demander_permissions(None)
            
            # Should have tried specific, failed, then tried generic
            modules['android.content'].Intent.assert_called_with("ACTION_GENERIC")
            mock_app._impl.native.startActivity.assert_called()

    def test_not_android_ignored(self, config_manager, mock_app):
        # No need to mock android libs here as logic returns early
        with patch('toga.platform.current_platform', 'windows'):
            config_manager.action_demander_permissions(None)
            mock_app._impl.native.startActivity.assert_not_called()
