import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
import tempfile
from drimesyncunofficial.uploads_manual import ManualUploadManager
class TestManualUploadManager:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.config_data = {'api_key': 'fake_key', 'workers': 2}
        app.workspace_list_cache = [{'id': 1, 'name': 'Work'}]
        app.loop = MagicMock()
        app.loop.call_soon_threadsafe = lambda x: x() 
        return app
    @pytest.fixture
    def upload_manager(self, mock_app):
        with patch('toga.Window'), patch('toga.Box'), patch('toga.Label'), \
             patch('toga.Button'), patch('toga.Selection'), patch('toga.MultilineTextInput'):
            manager = ManualUploadManager(mock_app)
            manager.lbl_progress = MagicMock()
            manager.txt_logs = MagicMock()
            manager.selection_ws = MagicMock()
            manager.selection_ws.value = "Espace Personnel (ID: 0)"
            return manager
    def test_get_local_manual_selection_file(self, upload_manager):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"content")
            tmp_path = tmp.name
        try:
            selection = [tmp_path]
            result = upload_manager.get_local_manual_selection(selection)
            rel_path = os.path.basename(tmp_path)
            assert rel_path in result
            assert result[rel_path]['full_path'] == tmp_path
            assert result[rel_path]['size'] == 7
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    def test_generate_report(self, upload_manager):
        stats = {
            'success': 10,
            'failed': 2,
            'skipped': 1,
            'bytes': 1024 * 1024, 
        }
        duration = 2.0
        final_status = "TERMINÉ"
        report = upload_manager.generate_report(stats, duration, final_status)
        assert "UPLOAD MANUEL TERMINÉ" in report
        assert "✅ Succès : 10" in report
        assert "❌ Échecs : 2" in report
        assert "1.00 Mo" in report 
        assert "512.00 Ko/s" in report 
    def test_upload_worker_success(self, upload_manager):
        local_info = {
            "full_path": "dummy_path",
            "size": 100,
            "mtime": 1234567890,
            "partial_hash": "hash"
        }
        
        # Mock api_client.upload_file
        upload_manager.app.api_client.upload_file.return_value = {"id": 100, "name": "uploaded.txt"}
        
        
        # Add task to queue
        # upload_manager.app.config_data is a dict, so get() works naturally.
        
        # We test internal logic of worker only
        queue = MagicMock()
        queue.get_nowait.side_effect = [("file.txt", local_info), Exception("Empty")]
        result_queue = MagicMock()
        
        upload_manager.upload_worker_manual(queue, result_queue, "key", "0", False)
        
        # Assert upload_file called
        upload_manager.app.api_client.upload_file.assert_called_once()
        args, kwargs = upload_manager.app.api_client.upload_file.call_args
        assert kwargs['relative_path'] == "file.txt"
        
        # Assert result put in queue
        result_queue.put.assert_called()
        res_args = result_queue.put.call_args[0][0]
        assert res_args[0] == "file.txt"
        assert res_args[1]['id'] == 100