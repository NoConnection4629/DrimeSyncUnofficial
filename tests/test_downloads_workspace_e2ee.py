import pytest
import asyncio
import sys
from unittest.mock import MagicMock, patch, mock_open, AsyncMock

# Toga Mock BEFORE imports that use it
if 'toga' not in sys.modules:
    toga_mock = MagicMock()
    sys.modules['toga'] = toga_mock

from drimesyncunofficial.downloads_workspace_e2ee import WorkspaceDownloadE2EEManager

class TestDownloadsWorkspaceE2EE:
    @pytest.fixture
    def manager(self):
        app = MagicMock()
        app.config_data = {'encryption_mode': 'advanced', 'e2ee_password': 'pass'}
        app.paths = MagicMock()
        loop = MagicMock()
        loop.run_in_executor = MagicMock()
        async def async_run(executor, func, *args):
            return func(*args)
        loop.run_in_executor.side_effect = async_run
        asyncio.get_running_loop = MagicMock(return_value=loop)
        manager = WorkspaceDownloadE2EEManager(app)
        manager.e2ee_key = b'key'
        manager.semaphore = asyncio.Semaphore(5)
        return manager

    def test_collect_tasks_recursive(self, manager):
        async def run_test():
            data_root = {
                "data": [
                    {"id": "folder1", "name": "folder1", "type": "folder", "size": 0},
                    {"id": "file1", "name": "ENC_file1.txt", "type": "file", "size": 100, "hash": "hash1"}
                ]
            }
            # Mock base_url
            manager.app.api_client.api_base_url = "http://api"
            manager.is_cancelled = False
            
            manager.app.api_client.get_file_entry.return_value = MagicMock(status_code=200, json=lambda: {"hash": "hash1"})
            with patch('drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_name') as mock_decrypt, \
                 patch('pathlib.Path.mkdir'), \
                 patch('pathlib.Path.exists', return_value=False):
                mock_decrypt.side_effect = lambda n, k: n.replace("ENC_", "") 
                tasks = []
                data_empty = {"data": []}
                manager.app.api_client.list_files.side_effect = [data_root, data_empty]
                
                # Signature: folder_id, folder_name, parent_path, ws_id, task_list
                await manager.collect_tasks_recursive("0", "root", "/tmp", "0", tasks)
                
                assert len(tasks) == 1
                assert tasks[0]['name'] == "file1.txt"
                assert "hash1" in tasks[0]['url']
        asyncio.run(run_test())

    def test_download_worker_bounded(self, manager):
        async def run_test():
            file_info = {
                "url": "http://test/dl",
                "path": "/tmp/file.txt",
                "name": "file.txt",
                "size": 100
            }
            manager.processed_files_count = 0
            manager.is_cancelled = False
            
            with patch.object(manager, '_download_file_worker', return_value=(True, "OK", 100)) as mock_worker:
                res = await manager._download_worker_bounded(file_info)
                assert res['status'] == 'success'
                assert res['bytes'] == 100
                mock_worker.assert_called_once_with("http://test/dl", "/tmp/file.txt", "file.txt", 100)
        asyncio.run(run_test())

    def test_0_renamed_handling(self, manager):
        async def run_test():
            data_root = {
                "data": [
                    {"id": "folder0", "name": "0.renamed", "type": "folder", "size": 0}
                ]
            }
            data_child = {"data": []}
            manager.app.api_client.list_files.side_effect = [data_root, data_child]
            tasks = []
            
            with patch('drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_name', side_effect=lambda n, k: n), \
                 patch('pathlib.Path.mkdir'), \
                 patch('pathlib.Path.exists', return_value=False):
                 
                 await manager.collect_tasks_recursive("root_id", "root", "/tmp", "ws_id", tasks)
                 assert manager.app.api_client.list_files.call_count == 2
        asyncio.run(run_test())