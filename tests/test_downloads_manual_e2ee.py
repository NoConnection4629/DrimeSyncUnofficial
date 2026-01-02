import pytest
from unittest.mock import MagicMock, patch, call, mock_open, AsyncMock
import os
import sys
import asyncio

# Toga Mock BEFORE imports that use it
if 'toga' not in sys.modules:
    toga_mock = MagicMock()
    sys.modules['toga'] = toga_mock

# Ensure drimesyncunofficial.downloads_manual_e2ee can be imported
from drimesyncunofficial.downloads_manual_e2ee import ManualDownloadE2EEManager
from drimesyncunofficial.utils import MODE_E2EE_ADVANCED

class TestDownloadsManualE2EE:
    @pytest.fixture
    def manager(self):
        app = MagicMock()
        app.config_data = {
            'api_key': 'test_key',
            'encryption_mode': MODE_E2EE_ADVANCED,
            'e2ee_password': 'password'
        }
        app.paths = MagicMock()
        app.paths.data = MagicMock()
        app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
        
        loop = MagicMock()
        loop.run_in_executor = MagicMock()
        async def async_run(executor, func, *args):
            return func(*args)
        
        loop.run_in_executor.side_effect = async_run
        asyncio.get_running_loop = MagicMock(return_value=loop)
        app.api_client = MagicMock()
        
        with patch('drimesyncunofficial.downloads_manual_e2ee.toga'):
            with patch('drimesyncunofficial.downloads_manual_e2ee.generate_or_load_salt', return_value=b'salt'):
                with patch('drimesyncunofficial.downloads_manual_e2ee.derive_key', return_value=b'key'):
                    mgr = ManualDownloadE2EEManager(app)
                    mgr.e2ee_key = b'key'
                    mgr.window = MagicMock()
                    mgr.lbl_progress = MagicMock()
                    mgr.txt_logs = MagicMock()
                    mgr.btn_download_action = MagicMock()
                    mgr.box_controls = MagicMock()
                    mgr.btn_pause = MagicMock()
                    mgr.btn_cancel = MagicMock()
                    mgr.sel_ws = MagicMock()
                    mgr.sel_ws.value = "Test (ID: 123)"
                    mgr.download_target_folder = "/tmp/target"
                    return mgr

    def test_download_file_worker(self, manager):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = [b"encrypted_content"]
        mock_resp.headers = {'content-length': '100'}
        mock_resp.headers = {'content-length': '100'}
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        manager.app.api_client.get_download_stream.return_value = mock_resp
        
        manager.total_size = 100
        manager.total_downloaded_bytes = 0
        
        # Args: url, save_path, file_name, total_size
        args = ("http://url", "/tmp/target/file.txt", "file.txt", 100)
        
        with patch('drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_file', return_value=b"decrypted_content") as mock_decrypt_file, \
             patch('builtins.open', new_callable=mock_open) as mock_file, \
             patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.path.exists', return_value=True), \
             patch('os.unlink'), \
             patch('os.makedirs'), \
             patch('pathlib.Path.read_bytes', return_value=b"encrypted_content_from_file"), \
             patch('drimesyncunofficial.base_download_manager.ensure_long_path_aware', side_effect=lambda x: x):
            
            mock_temp.return_value.__enter__.return_value.name = "/tmp/enc_file"
            
            res, msg, size = manager._download_file_worker(*args)
            
            assert res is True, f"Worker Failed: {msg}"
            mock_decrypt_file.assert_called_with(b"encrypted_content_from_file", manager.e2ee_key)
            mock_file.assert_called_with("/tmp/target/file.txt", "wb")
            mock_file().write.assert_called_with(b"decrypted_content")

    def test_collect_tasks_recursive(self, manager):
        async def run_test():
            # mock_resp should be the dict directly if list_files returns data, 
            # OR if list_files returns response, BaseDownloadManager calls .json().
            # Looking at BaseDownloadManager.collect_tasks_recursive:
            # data = await loop.run_in_executor(None, do_list)
            # do_list calls api_client.list_files.
            # Real api_client.list_files returns a dictionary (parsed JSON).
            # So we should return the dict directly.
            manager.app.api_client.list_files.return_value = {
                "data": [
                    {"id": "file1", "name": "ENC_file1.txt", "type": "file", "size": 100, "hash": "hash1"}
                ]
            }
            tasks = []
            
            with patch('drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_name', side_effect=lambda n, k: n.replace("ENC_", "")), \
                 patch('drimesyncunofficial.base_download_manager.ensure_long_path_aware', side_effect=lambda x: x):
                await manager.collect_tasks_recursive("folder_id", "folder_name", "/tmp/target", "ws_id", tasks)
                
            assert len(tasks) == 1
            assert tasks[0]['name'] == "file1.txt"
            
            expected_path = os.path.normpath("/tmp/target/folder_name/file1.txt")
            actual_path = os.path.normpath(tasks[0]['path'])
            assert actual_path == expected_path

        asyncio.run(run_test())

    def test_start_download_recursive(self, manager):
        async def run_test():
            selection = [{"id": "folder1", "name": "folder1", "type": "folder"}]
            with patch.object(manager, 'collect_tasks_recursive') as mock_collect:
                async def side_effect(fid, fname, path, wsid, tasks):
                    tasks.append({"name": "file1", "path": "/tmp/file1", "size": 10, "url": "http://dl"})
                mock_collect.side_effect = side_effect
                
                # Mock worker related
                with patch.object(manager, '_download_worker_bounded', new_callable=MagicMock) as mock_worker:
                    # _download_worker_bounded is async
                    async def worker_side_effect(info): return {'status': 'success'}
                    mock_worker.side_effect = worker_side_effect
                    
                    manager.lbl_status = MagicMock()
                    manager._fetch_file_hash = AsyncMock() # Prevent real calls
                    
                    # Mock dialog to be awaitable
                    async def mock_dialog(*args, **kwargs): return True
                    manager.app.main_window.dialog = AsyncMock(side_effect=mock_dialog)

                    await manager.start_download(target_folder="/tmp", selection=selection)
                    
                    mock_collect.assert_called()
                    assert mock_worker.call_count == 1
                    
        asyncio.run(run_test())
