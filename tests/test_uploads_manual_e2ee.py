import pytest
from unittest.mock import MagicMock, patch, call, mock_open
import os
import asyncio
from drimesyncunofficial.uploads_manual_e2ee import ManualUploadE2EEManager
from drimesyncunofficial.utils import MODE_E2EE_ADVANCED
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'test_key',
        'encryption_mode': MODE_E2EE_ADVANCED,
        'e2ee_password': 'password'
    }
    app.paths = MagicMock()
    app.paths.data = MagicMock()
    app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
    def mock_create_task(coro):
        if asyncio.iscoroutine(coro): coro.close()
        return MagicMock()
    app.loop.create_task = MagicMock(side_effect=mock_create_task)
    app.api_client = MagicMock()
    return app
@pytest.fixture
def manager(mock_app):
    with patch('drimesyncunofficial.uploads_manual_e2ee.toga'):
        with patch('drimesyncunofficial.uploads_manual_e2ee.generate_or_load_salt', return_value=b'salt'):
            with patch('drimesyncunofficial.uploads_manual_e2ee.derive_key', return_value=b'key'):
                mgr = ManualUploadE2EEManager(mock_app)
                mgr.e2ee_key = b'key'
                mgr.window = MagicMock()
                mgr.lbl_progress = MagicMock()
                mgr.txt_logs = MagicMock()
                mgr.btn_upload_action = MagicMock()
                mgr.box_controls = MagicMock()
                mgr.btn_pause = MagicMock()
                mgr.btn_cancel = MagicMock()
                mgr.sel_ws = MagicMock()
                mgr.sel_ws.value = "Test (ID: 123)"
                return mgr
class TestUploadsManualE2EE:
    @patch('drimesyncunofficial.uploads_manual_e2ee.E2EE_encrypt_file')
    @patch('drimesyncunofficial.uploads_manual_e2ee.E2EE_encrypt_name')
    @patch('pathlib.Path.stat')
    def test_upload_simple_e2ee(self, mock_stat, mock_encrypt_name, mock_encrypt_file, manager):
        local_info = {"full_path": "/local/file.txt", "size": 100, "mtime": 1000, "partial_hash": "h1"}
        mock_encrypt_name.side_effect = lambda n, k: f"ENC_{n}"
        mock_encrypt_file.return_value = b"encrypted_content"
        manager.app.api_client.upload_simple.return_value.status_code = 200
        manager.app.api_client.upload_simple.return_value.json.return_value = {
            "fileEntry": {"id": "new_id"}
        }
        res = manager.upload_simple_e2ee(local_info, "remote/file.txt", "key", "ws_id", "thread")
        assert res is not None
        assert res['id'] == "new_id"
        mock_encrypt_file.assert_called_with("/local/file.txt", b'key')
        manager.app.api_client.upload_simple.assert_called()