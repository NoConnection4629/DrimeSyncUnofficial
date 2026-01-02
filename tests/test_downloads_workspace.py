import pytest
from unittest.mock import MagicMock, patch, call, mock_open, AsyncMock
import asyncio
import sys

# Toga Mock BEFORE imports that use it
if 'toga' not in sys.modules:
    toga_mock = MagicMock()
    sys.modules['toga'] = toga_mock

from drimesyncunofficial.downloads_workspace import WorkspaceDownloadManager
import pathlib

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {'workers': 5, 'api_key': 'k', 'encryption_mode': 'standard', 'e2ee_password': 'p'}
    app.api_client = MagicMock()
    app.paths = MagicMock()
    app.loop = MagicMock()
    app.loop.run_in_executor = MagicMock()
    app.is_mobile = False
    return app

def test_collect_tasks_recursive(mock_app):
    async def run_test():
        manager = WorkspaceDownloadManager(mock_app)
        data_root = {
            "data": [
                {"id": "1", "name": "file1.txt", "type": "file", "size": 1024, "hash": "h1"},
                {"id": "2", "name": "subfolder", "type": "folder"}
            ]
        }
        data_sub = {"data": []}
        mock_app.api_client.list_files.side_effect = [data_root, data_sub]
        mock_app.api_client.api_base_url = "http://api"
        
        # Ensure is_cancelled is init
        manager.is_cancelled = False
        
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.exists', return_value=False):
            mock_loop = MagicMock()
            mock_loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *args: f(*args) if callable(f) else f)
            mock_get_loop.return_value = mock_loop
            tasks = []
            
            # Signature: folder_id, folder_name, parent_path, ws_id, task_list
            await manager.collect_tasks_recursive("0", "root", "/tmp", "123", tasks)
            
            assert len(tasks) == 1
            assert tasks[0]['name'] == "file1.txt"
            assert "h1" in tasks[0]['url']
            assert mock_app.api_client.list_files.call_count == 2
    asyncio.run(run_test())

def test_download_file_worker(mock_app):
    manager = WorkspaceDownloadManager(mock_app)
    manager.lbl_progress = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-length': '1024'}
    mock_resp.iter_content.return_value = [b'chunk1', b'chunk2']
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_app.api_client.get_download_stream.return_value = mock_resp
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.unlink'):
        success, msg, size = manager._download_file_worker("http://url", "/tmp/file.txt", "file.txt", 0)
        assert success is True
        assert size == 0 # passed 0, returns 0
        mock_app.api_client.get_download_stream.assert_called_once_with("http://url")
        mock_file().write.assert_called()

if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))