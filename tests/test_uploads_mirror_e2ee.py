import pytest
from unittest.mock import MagicMock, patch, call
import os
import asyncio
from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager
from drimesyncunofficial.utils import MODE_E2EE_STANDARD, MODE_E2EE_ZK, MODE_E2EE_ADVANCED
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'test_key',
        'workers': 1,
        'semaphores': 1,
        'use_exclusions': True,
        'encryption_mode': MODE_E2EE_ADVANCED, 
        'e2ee_password': 'password'
    }
    app.paths = MagicMock()
    app.paths.data = MagicMock()
    app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
    def mock_create_task(coro):
        if asyncio.iscoroutine(coro):
            coro.close()
        return MagicMock()
    app.loop.create_task = MagicMock(side_effect=mock_create_task)
    app.api_client = MagicMock()
    app.api_client.list_files.return_value.status_code = 200
    app.api_client.list_files.return_value.json.return_value = {"data": []}
    return app
@pytest.fixture
def mirror_e2ee_manager(mock_app):
    with patch('drimesyncunofficial.uploads_mirror_e2ee.toga'):
        with patch('drimesyncunofficial.uploads_mirror_e2ee.generate_or_load_salt', return_value=b'salt'):
            with patch('drimesyncunofficial.uploads_mirror_e2ee.derive_key', return_value=b'key'):
                manager = MirrorUploadE2EEManager(mock_app)
                manager.e2ee_key = b'key' 
                manager.lbl_progress = MagicMock()
                manager.txt_logs = MagicMock()
                manager.window = MagicMock()
                manager.btn_sync = MagicMock()
                manager.btn_simu = MagicMock()
                manager.btn_force = MagicMock()
                manager.btn_pause = MagicMock()
                manager.btn_cancel = MagicMock()
                manager.box_controls = MagicMock()
                manager.box_secondary_btns = MagicMock()
                manager.lbl_warning_ws = MagicMock()
                manager.lbl_conflict_warning = MagicMock()
                manager.selection_mirror_ws = MagicMock()
                manager.selection_mirror_ws.value = "Test (ID: 0)"
                return manager
class TestMirrorUploadE2EE:
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.E2EE_encrypt_name')
    def test_dry_run_obfuscation(self, mock_encrypt_name, mock_load_cloud, mock_get_local, mirror_e2ee_manager):
        """Test that dry run calculates encrypted paths correctly."""
        mock_encrypt_name.side_effect = lambda name, key: f"ENC_{name}"
        mock_get_local.return_value = {
            "folders": set(),
            "files": {
                "secret.txt": {"partial_hash": "hash1", "size": 100, "mtime": 1000, "full_path": "/local/secret.txt"}
            }
        }
        mock_load_cloud.return_value = {"folders": {}, "files": {}}
        mirror_e2ee_manager._thread_mirror_logic("/local", "0", is_dry_run=True, force_sync=False)
        pass
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.E2EE_encrypt_name')
    def test_folder_creation_dry_run(self, mock_encrypt_name, mock_load_cloud, mock_get_local, mirror_e2ee_manager):
        mirror_e2ee_manager.e2ee_mode = MODE_E2EE_ZK
        mock_encrypt_name.side_effect = lambda name, key: f"ENC_{name}"
        mock_get_local.return_value = {
            "folders": set(["secret_folder"]),
            "files": {}
        }
        mock_load_cloud.return_value = {"folders": {}, "files": {}}
        mirror_e2ee_manager._thread_mirror_logic("/local", "0", is_dry_run=True, force_sync=False)
        mock_encrypt_name.assert_called_with("secret_folder", b'key')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.upload_simple_e2ee')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.E2EE_encrypt_name')
    def test_real_sync_upload_encrypted(self, mock_encrypt_name, mock_upload_simple, mock_load_cloud, mock_get_local, mirror_e2ee_manager):
        """Test that real sync triggers encrypted upload."""
        mock_encrypt_name.side_effect = lambda name, key: f"ENC_{name}"
        mock_get_local.return_value = {
            "folders": set(),
            "files": {
                "secret.txt": {"partial_hash": "hash1", "size": 100, "mtime": 1000, "full_path": "/local/secret.txt"}
            }
        }
        mock_load_cloud.return_value = {"folders": {}, "files": {}}
        mock_upload_simple.return_value = {"id": "new_id", "size": 100}
        mirror_e2ee_manager._thread_mirror_logic("/local", "0", is_dry_run=False, force_sync=False)
        mock_upload_simple.assert_called_once()
        args, _ = mock_upload_simple.call_args
        assert args[1] == "ENC_secret.txt"
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.E2EE_encrypt_name')
    def test_real_sync_delete_encrypted(self, mock_encrypt_name, mock_load_cloud, mock_get_local, mirror_e2ee_manager):
        """Test that real sync triggers deletion of encrypted files."""
        mock_get_local.return_value = {"folders": set(), "files": {}}
        mock_load_cloud.return_value = {
            "folders": {},
            "files": {
                "ENC_deleted.txt": {"partial_hash": "hash3", "size": 300, "id": "del_id"}
            }
        }
        mirror_e2ee_manager._thread_mirror_logic("/local", "0", is_dry_run=False, force_sync=False)
        mirror_e2ee_manager.app.api_client.delete_entries.assert_called_once()
        args, kwargs = mirror_e2ee_manager.app.api_client.delete_entries.call_args
        assert "del_id" in kwargs.get('entry_ids', []) or "del_id" in args[0]
    @patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager.upload_file_router_e2ee')
    def test_upload_worker_calls_router(self, mock_router, mirror_e2ee_manager):
        """Test that upload_worker delegates to upload_file_router_e2ee."""
        from queue import Queue
        q = Queue()
        res_q = Queue()
        item_info = {"size": 100, "full_path": "/local/file.txt"}
        q.put(("/local/file.txt", item_info))
        mirror_e2ee_manager.stop_event.set()
        mirror_e2ee_manager.stop_event.clear()
        mirror_e2ee_manager.upload_worker(q, res_q, "key", "ws_id")
        mock_router.assert_called_once()
        args, _ = mock_router.call_args
        assert args[0] == item_info
    def test_0_renamed_logic(self, mirror_e2ee_manager):
        """Test that '0' is renamed to '0.renamed' in unencrypted parts."""
        res = mirror_e2ee_manager._calculate_remote_path("folder/0/file.txt", is_folder=False)
        mirror_e2ee_manager.e2ee_mode = MODE_E2EE_ADVANCED
        mirror_e2ee_manager.e2ee_key = b'key'
        res = mirror_e2ee_manager._calculate_remote_path("path/to/0", is_folder=True)
        assert res == "path/to/0.renamed"
        res = mirror_e2ee_manager._calculate_remote_path("path/0/file.txt", is_folder=False)
        assert "0.renamed" in res.split("/")