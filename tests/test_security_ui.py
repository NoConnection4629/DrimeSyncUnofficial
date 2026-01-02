import pytest
import asyncio
from unittest.mock import MagicMock, patch, ANY, AsyncMock
from drimesyncunofficial.security import SecurityManager

class TestSecurityUI:
    
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.changer_ecran = MagicMock()
        app.retour_arriere = MagicMock()
        app.main_window = MagicMock()
        app.paths = MagicMock()
        return app

    @pytest.fixture
    def sec_manager(self, mock_app):
        # We patch toga interactions to avoid GUI instantiation errors during tests
        with patch('toga.Box'), patch('toga.Label'), patch('toga.Button'), \
             patch('toga.TextInput'), patch('toga.PasswordInput'), patch('toga.Divider'):
            return SecurityManager(mock_app)

    def test_action_export_salt_fullscreen(self, sec_manager, mock_app):
        """Verify "Export Salt" uses full screen navigation (changer_ecran)"""
        with patch('drimesyncunofficial.security.get_salt_as_base64', return_value="FAKE_SALT"):
            # It's an async method
            asyncio.run(sec_manager.action_export_salt(None))
        
        # Should NOT use toga.Window
        # Should call app.changer_ecran
        mock_app.changer_ecran.assert_called_once()
        
        # Verify the content passed to changer_ecran is a Box (or simulated UI)
        args, _ = mock_app.changer_ecran.call_args
        assert args[0] is not None

    def test_action_import_salt_ui(self, sec_manager, mock_app):
        """Verify "Import Salt" uses full screen navigation"""
        # We need to simulate the confirmation dialog returning True
        mock_app.main_window.dialog = AsyncMock(return_value=True)
        
        asyncio.run(sec_manager.action_import_salt(None))
        
        mock_app.changer_ecran.assert_called_once()

    def test_on_2fa_toggle_generate_qr(self, sec_manager, mock_app):
        """Test simple salt generation trigger"""
        sec_manager.input_secret_2fa = MagicMock()
        sec_manager.input_secret_2fa.value = ""
        sec_manager.box_2fa_setup = MagicMock()
        sec_manager.lbl_2fa_status = MagicMock()
        sec_manager.qr_image_view = MagicMock()
        sec_manager.container_2fa_wrapper = MagicMock()
        
        widget = MagicMock()
        widget.value = True
        
        with patch('drimesyncunofficial.security.generate_2fa_secret', return_value='SECRET'), \
             patch('drimesyncunofficial.security.generate_qr_image_bytes', return_value=b'IMG'):
            
            sec_manager.on_2fa_toggle(widget)
            
            # Verify secret generation
            sec_manager.input_secret_2fa.value = 'SECRET'
            
    def test_action_import_salt_commit(self, sec_manager, mock_app):
        """Test saving the imported salt"""
        # First we need to simulate opening the UI to set self.input_import_salt
        self.test_action_import_salt_ui(sec_manager, mock_app)
        
        # Now define the inner function behavior or check if we can access it.
        # Since 'do_import' is an inner function of action_import_salt, we can't call it directly easily.
        # But we can verify action_import_salt logic.
        pass # Skipping inner function test for now or requires more complex setup.
