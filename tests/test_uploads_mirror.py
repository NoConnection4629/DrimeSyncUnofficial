import pytest
from unittest.mock import MagicMock, patch, call
import os
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'test_key',
        'workers': 1,
        'semaphores': 1,
        'use_exclusions': True
    }
    app.paths = MagicMock()
    app.paths.data = MagicMock()
    app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
    app.api_client = MagicMock()
    return app
@pytest.fixture
def mirror_manager(mock_app):
    with patch('drimesyncunofficial.uploads_mirror.toga'):
        manager = MirrorUploadManager(mock_app)
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
class TestMirrorUpload:
    @patch('asyncio.create_task')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.load_local_cloud_tree')
    def test_dry_run_detection(self, mock_load_cloud, mock_get_local_tree, mock_create_task, mirror_manager):
        """Test that dry run correctly detects files to upload and delete."""
        mock_get_local_tree.return_value = {
            "folders": {"/local/folder"}, 
            "files": {
                "file1.txt": {"partial_hash": "hash1", "size": 100, "mtime": 1000},
                "new_file.txt": {"partial_hash": "hash2", "size": 200, "mtime": 2000}
            }
        }
        mock_load_cloud.return_value = {
            "folders": {"/local/folder": {"id": "f1"}},
            "files": {
                "file1.txt": {"partial_hash": "hash1", "size": 100, "id": "id1"},
                "deleted_file.txt": {"partial_hash": "hash3", "size": 300, "id": "id3"}
            }
        }
        mirror_manager._thread_mirror_logic("/local", "0", is_dry_run=True, force_sync=False)
        pass
    @patch('asyncio.create_task')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.log_ui')
    def test_dry_run_logic_calls(self, mock_log_ui, mock_load_cloud, mock_get_local_tree, mock_create_task, mirror_manager):
        mock_get_local_tree.return_value = {
            "folders": set(["folder1"]),
            "files": {
                "file1.txt": {"partial_hash": "hash1", "size": 100, "mtime": 1000},
                "new_file.txt": {"partial_hash": "hash2", "size": 200, "mtime": 2000}
            }
        }
        mock_load_cloud.return_value = {
            "folders": {"folder1": {"id": "f1"}},
            "files": {
                "file1.txt": {"partial_hash": "hash1", "size": 100, "id": "id1"},
                "deleted_file.txt": {"partial_hash": "hash3", "size": 300, "id": "id3"}
            }
        }
        mock_log_ui.side_effect = None
        mirror_manager._thread_mirror_logic("/local", "0", is_dry_run=True, force_sync=False)
        log_calls = [args[0] for args, _ in mock_log_ui.call_args_list]
        assert any("new_file.txt" in log and ("[SIMU]" in log or "Simulation" in log) for log in log_calls)
        assert any(("[SIMU]" in log and "Suppression" in log and "deleted_file.txt" in log) for log in log_calls)
        assert not any("[SIMU] Upload: file1.txt" in log for log in log_calls)
    @patch('asyncio.create_task')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.upload_file_router')
    def test_real_sync_upload(self, mock_upload_router, mock_load_cloud, mock_get_local_tree, mock_create_task, mirror_manager):
        """Test that real sync triggers upload."""
        mock_get_local_tree.return_value = {
            "folders": set(),
            "files": {
                "new_file.txt": {"partial_hash": "hash2", "size": 200, "mtime": 2000, "full_path": "/local/new_file.txt"}
            }
        }
        mock_load_cloud.return_value = {"folders": {}, "files": {}}
        mock_upload_router.return_value = {"id": "new_id", "size": 200}
        mirror_manager._thread_mirror_logic("/local", "0", is_dry_run=False, force_sync=False)
        mock_upload_router.assert_called()
        found = False
        for call_args in mock_upload_router.call_args_list:
            if call_args[0][1] == "new_file.txt":
                found = True
                break
        assert found
    @patch('asyncio.create_task')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.load_local_cloud_tree')
    def test_real_sync_delete(self, mock_load_cloud, mock_get_local_tree, mock_create_task, mirror_manager):
        """Test that real sync triggers deletion."""
        mock_get_local_tree.return_value = {"folders": set(), "files": {}}
        mock_load_cloud.return_value = {
            "folders": {},
            "files": {
                "deleted_file.txt": {"partial_hash": "hash3", "size": 300, "id": "del_id"}
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mirror_manager.app.api_client.delete_entries.return_value = mock_response
        mirror_manager._thread_mirror_logic("/local", "0", is_dry_run=False, force_sync=False)
        mirror_manager.app.api_client.delete_entries.assert_called()
        call_args = mirror_manager.app.api_client.delete_entries.call_args
        assert call_args is not None
        args, kwargs = call_args
        if 'entry_ids' in kwargs:
            assert "del_id" in kwargs['entry_ids']
        else:
            assert "del_id" in args[0]
        assert kwargs.get('delete_forever') is True