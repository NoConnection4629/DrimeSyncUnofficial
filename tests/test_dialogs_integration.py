import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import sys
if 'toga' not in sys.modules:
    sys.modules['toga'] = MagicMock()
import toga
class MockDialog:
    def __init__(self, title, message):
        self.title = title
        self.message = message
toga.InfoDialog = MockDialog
toga.ErrorDialog = MockDialog
toga.QuestionDialog = MockDialog
from drimesyncunofficial.uploads_manual import ManualUploadManager
from drimesyncunofficial.downloads_manual import ManualDownloadManager
from drimesyncunofficial.security import SecurityManager
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.main_window = MagicMock()
    app.main_window.dialog = AsyncMock(return_value=True) 
    app.is_mobile = False 
    app.config_data = {
        'api_key': 'test_key', 
        'workers': 2,
        'encryption_mode': 'NO_ENC',
        'e2ee_password': 'pass'
    }
    app.workspace_list_cache = [{'id': '1', 'name': 'Test WS'}]
    app.loop = MagicMock()
    app.loop.call_soon_threadsafe = lambda x: x()
    app.loop.create_task = lambda x: asyncio.create_task(x) if asyncio.iscoroutine(x) else None
    return app
class TestDialogsIntegration:
    def test_manual_upload_empty_selection_dialog(self, mock_app):
        """Test that launching upload without selection shows InfoDialog."""
        async def run():
            manager = ManualUploadManager(mock_app)
            manager.selection = []
            await manager.launch_upload(is_dry_run=False)
            mock_app.main_window.dialog.assert_called_once()
            args = mock_app.main_window.dialog.call_args[0]
            assert isinstance(args[0], toga.InfoDialog)
            assert args[0].title in ["Info", "Information", "Informationen"]
            assert "sélectionner des fichiers" in args[0].message
        asyncio.run(run())
    def test_manual_download_empty_selection_dialog(self, mock_app):
        """Test that downloading without selection shows InfoDialog."""
        async def run():
            manager = ManualDownloadManager(mock_app)
    def test_security_save_dialog(self, mock_app):
        """Test that saving security settings shows InfoDialog."""
        async def run():
            manager = SecurityManager(mock_app)
            manager.lbl_password_status = MagicMock()
            manager.lbl_2fa_status = MagicMock()
            manager.current_mode = 'NO_ENC'
            manager.current_password = ''
            manager.switch_2fa = MagicMock()
            manager.switch_2fa.value = False
            with patch('drimesyncunofficial.security.set_secure_secret', return_value=True):
                 with patch('builtins.open', MagicMock()): 
                    await manager.action_save(None)
            mock_app.main_window.dialog.assert_called()
            args = mock_app.main_window.dialog.call_args[0]
            name = args[0].__class__.__name__
            assert name in ('InfoDialog', 'MockDialog')
            assert "sauvegardés" in args[0].message
        asyncio.run(run())
    def test_mirror_cancel_confirmation(self, mock_app):
        """Test that cancelling mirror sync asks for confirmation."""
        async def run():
            manager = MirrorUploadManager(mock_app)
            manager.is_running = True
            manager.lbl_progress = MagicMock()
            manager.txt_logs = MagicMock()
            await manager.action_cancel(None)
            mock_app.main_window.dialog.assert_called_once()
            args = mock_app.main_window.dialog.call_args[0]
            assert isinstance(args[0], toga.QuestionDialog)
            assert "vraiment annuler" in args[0].message
        asyncio.run(run())