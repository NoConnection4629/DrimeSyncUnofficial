import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from drimesyncunofficial.app import DrimeSyncUnofficial
from drimesyncunofficial.constants import COL_VERT

class TestAppStartup:
    
    @pytest.fixture
    def app(self):
        # Create a dummy base class to replace toga.App
        class DummyApp:
            def __init__(self, *args, **kwargs):
                pass
                
        # Patch toga.App with DummyApp so DrimeSyncUnofficial inherits from IT
        # This ensures real methods of DrimeSyncUnofficial are preserved
        with patch('drimesyncunofficial.app.toga.App', new=DummyApp):
            from drimesyncunofficial.app import DrimeSyncUnofficial
            
            # Re-import to ensure class uses patched parent
            import importlib
            import drimesyncunofficial.app
            importlib.reload(drimesyncunofficial.app)
            
            app_instance = drimesyncunofficial.app.DrimeSyncUnofficial()
            app_instance.paths = MagicMock()
            app_instance.paths.data = MagicMock()
            app_instance.main_window = MagicMock()
            app_instance.lbl_status = MagicMock()
            
            # Since we inherit from DummyApp, we need to manually mock methods 
            # that are expected to exist on self (like main_window.dialog etc if used)
            # But here we are testing startup() which is defined on the subclass.
            
            yield app_instance

    def test_startup_no_2fa(self, app):
        """Test startup flow without 2FA configured"""
        app.charger_config = MagicMock(return_value={'api_key': 'test', '2fa_secret': ''})
        app.show_main_app = MagicMock()
        app.show_login_screen = MagicMock()
        
        # Patch dependencies ensuring they are the ones used in the reloaded module
        with patch('drimesyncunofficial.app.DrimeAPIClient'), \
             patch('drimesyncunofficial.app.prevent_windows_sleep'), \
             patch('drimesyncunofficial.app.toga.MainWindow'):
            
            app.startup()
            
            # Should show main app directly
            app.show_main_app.assert_called_once()
            app.show_login_screen.assert_not_called()

    def test_startup_with_2fa(self, app):
        """Test startup flow WITH 2FA configured"""
        app.charger_config = MagicMock(return_value={'api_key': 'test', '2fa_secret': 'SECRET'})
        app.show_main_app = MagicMock()
        app.show_login_screen = MagicMock()
        
        with patch('drimesyncunofficial.app.DrimeAPIClient'), \
             patch('drimesyncunofficial.app.prevent_windows_sleep'), \
             patch('drimesyncunofficial.app.toga.MainWindow'), \
             patch('drimesyncunofficial.app.get_secure_secret', return_value='SECRET'):
            
            app.startup()
            
            # Should show login screen
            app.show_login_screen.assert_called_once()
            app.show_main_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_api_success(self, app):
        """Test successful API verification on startup"""
        app.config_data = {'api_key': 'valid_key'}
        app.api_client = MagicMock()
        app.lbl_status.style = MagicMock() # Ensure style exists
        
        # Mock successful user response
        user_data = {'user': {'email': 'test@example.com'}}
        
        # Async mock for loop.run_in_executor
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(side_effect=[user_data, {'workspaces': []}])
            
            await app.verify_api_startup()
            
            # Status should be updated to Connected
            # Check text assignment
            assert "Connecté" in str(app.lbl_status.text)
            assert app.lbl_status.style.color == COL_VERT

    @pytest.mark.asyncio
    async def test_verify_api_failure(self, app):
        """Test failed API verification"""
        app.config_data = {'api_key': 'invalid_key'}
        app.api_client = MagicMock()
        app.lbl_status.style = MagicMock() 

        # Mock failure (None or error dict)
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value={'error': 'Invalid Key'})
            
            await app.verify_api_startup()
            
            # Status should indicate error
            assert "Invalide" in str(app.lbl_status.text) or "Erreur" in str(app.lbl_status.text)
            assert app.lbl_status.style.color == 'red'
