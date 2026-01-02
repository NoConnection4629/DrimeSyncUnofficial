import pytest
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
import sys
import asyncio
from pathlib import Path
class MockRow:
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)
        self._args = args
if 'toga' not in sys.modules:
    toga_mock = MagicMock()
    toga_mock.__path__ = []
    sys.modules['toga'] = toga_mock
if 'toga.sources' not in sys.modules:
    sources_mock = MagicMock()
    sources_mock.Row = MockRow
    sys.modules['toga.sources'] = sources_mock
    sys.modules['toga'].sources = sources_mock
from drimesyncunofficial.downloads_manual import ManualDownloadManager
class TestDownloadsManual:
    @pytest.fixture
    def manager(self):
        app = MagicMock()
        app.is_mobile = False
        app.config_data = {'workers': 5, 'semaphores': 0, 'api_key': 'test_key'}
        app.paths = MagicMock()
        app.paths.data = MagicMock()
        loop = MagicMock()
        async def async_run(executor, func, *args):
            return func(*args) if callable(func) else func
        loop.run_in_executor.side_effect = async_run
        loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
        app.loop = loop
        app.api_client = MagicMock()
        with patch('asyncio.get_running_loop', return_value=loop):
            mgr = ManualDownloadManager(app)
            mgr.window = MagicMock()
            mgr.lbl_status = MagicMock()
            mgr.table = MagicMock()
            mgr.box_actions = MagicMock()
            mgr.box_controls = MagicMock()
            mgr.btn_pause = MagicMock()
            mgr.lbl_progress = MagicMock()
            mgr.selection_ws = MagicMock()
            mgr.selection_ws.value = "Workspace (ID: 123)"
            mgr.update_status_ui = MagicMock()
            mgr._set_ui_downloading = MagicMock()
            mgr._download_worker_bounded = AsyncMock()
            return mgr
    def test_initialization(self, manager):
        assert manager.files_cache == []
        assert manager.current_folder_id is None
    def test_load_data_empty(self, manager):
        async def run_test():
            manager.app.api_client.list_files.return_value = {"data": []}
            await manager.load_content()
            assert manager.files_cache == []
            assert manager.lbl_status.text == "0 éléments."
            manager.app.api_client.list_files.assert_called_once()
        asyncio.run(run_test())
    def test_load_data_with_files(self, manager):
        async def run_test():
            mock_data = {
                "data": [
                    {"id": "1", "name": "file1.txt", "type": "file", "size": 1024},
                    {"id": "2", "name": "folder1", "type": "folder", "size": 0}
                ]
            }
            manager.app.api_client.list_files.return_value = mock_data
            await manager.load_content()
            assert len(manager.files_cache) == 2
            assert len(manager.table.data) == 2
            assert manager.table.data[0][0] == "file1.txt"
            assert manager.table.data[1][0] == "folder1"
        asyncio.run(run_test())
    def test_download_file_worker(self, manager):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'content-length': '1024'}
        mock_resp.iter_content.return_value = [b'chunk1', b'chunk2']
        mock_resp.__enter__.return_value = mock_resp
        async def run_test():
            manager.app.api_client.get_download_stream.return_value = mock_resp
            # Patch ensure_long_path_aware to return path as-is to avoid Windows \\?\ prefix issues in tests
            with patch('drimesyncunofficial.base_download_manager.ensure_long_path_aware', side_effect=lambda x: x):
                with patch('builtins.open', mock_open()) as mock_file:
                     # os.stat not used in new implementation, can remove patch or keep ignored
                     manager._download_file_worker("http://test/download", "/tmp/file", "file.txt", 1024)
                     mock_file.assert_called_with("/tmp/file", "wb")
                     mock_file().write.assert_called()
        asyncio.run(run_test())
if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))