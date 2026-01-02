import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from drimesyncunofficial.trash import TrashManager
class TestTrashManager:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.config_data = {'api_key': 'fake_key'}
        app.workspace_list_cache = [{'id': 1, 'name': 'Work'}]
        app.is_mobile = False
        app.api_client = MagicMock() 
        app.main_window = MagicMock()
        app.main_window.dialog = AsyncMock()
        return app
    @pytest.fixture
    def trash_manager(self, mock_app):
        with patch('toga.Window'), patch('toga.Box'), patch('toga.Label'), \
             patch('toga.Button'), patch('toga.Selection'), patch('toga.DetailedList'), \
             patch('toga.Table'):
            manager = TrashManager(mock_app)
            manager.selection_ws = MagicMock()
            manager.selection_ws.value = "Espace Personnel (ID: 0)"
            manager.status = MagicMock()
            manager.table = MagicMock()
            manager.table.data = []
            manager.list = MagicMock() 
            return manager
    @pytest.mark.asyncio
    async def test_load_data_success(self, trash_manager, mock_app):
        mock_data = {
            "data": [
                {"id": 101, "name": "deleted.txt", "size": 1024, "deleted_at": "2023-01-01T12:00:00", "type": "file"},
                {"id": 102, "name": "folder", "size": 0, "deleted_at": "2023-01-02T12:00:00", "type": "folder"}
            ]
        }
        mock_app.api_client.list_files.return_value = mock_data
        await trash_manager.load_data()
        assert len(trash_manager.trash_files_cache) == 2
        assert trash_manager.trash_files_cache[0]['name'] == "deleted.txt"
        assert len(trash_manager.table.data) == 2
    @pytest.mark.asyncio
    async def test_load_data_empty(self, trash_manager, mock_app):
        mock_app.api_client.list_files.return_value = {"data": []}
        await trash_manager.load_data()
        assert len(trash_manager.trash_files_cache) == 0
        assert len(trash_manager.table.data) == 0
    @pytest.mark.asyncio
    async def test_load_data_error(self, trash_manager, mock_app):
        mock_app.api_client.list_files.side_effect = Exception("500")
        await trash_manager.load_data()
        assert len(trash_manager.trash_files_cache) == 0
        assert "Aucune donnée" in trash_manager.status.text
    @pytest.mark.asyncio
    async def test_action_restore_no_selection(self, trash_manager, mock_app):
        trash_manager.get_selection = MagicMock(return_value=[])
        await trash_manager.action_restore(None)
        mock_app.main_window.dialog.assert_called_once() 
    @pytest.mark.asyncio
    async def test_action_restore_success(self, trash_manager, mock_app):
        selected_file = {"id": 101, "name": "restore_me.txt"}
        trash_manager.get_selection = MagicMock(return_value=[selected_file])
        mock_app.api_client.restore_entry.return_value = {}
        trash_manager.load_data = AsyncMock()
        await trash_manager.action_restore(None)
        mock_app.api_client.restore_entry.assert_called_with(["101"])
        trash_manager.load_data.assert_called_once()
        mock_app.main_window.dialog.assert_called() 
    @pytest.mark.asyncio
    async def test_action_delete_selected(self, trash_manager, mock_app):
        selected_file = {"id": 101, "name": "kill_me.txt"}
        trash_manager.get_selection = MagicMock(return_value=[selected_file])
        trash_manager.window = MagicMock()
        trash_manager.window.dialog = AsyncMock(return_value=True) 
        mock_app.api_client.delete_entries.return_value = {}
        trash_manager.load_data = AsyncMock()
        await trash_manager.action_delete_selected(None)
        mock_app.api_client.delete_entries.assert_called_with(["101"], delete_forever=True)
        trash_manager.load_data.assert_called_once()
    @pytest.mark.asyncio
    async def test_action_empty_trash(self, trash_manager, mock_app):
        trash_manager.trash_files_cache = [{"id": 1}, {"id": 2}]
        trash_manager.window = MagicMock()
        trash_manager.window.dialog = AsyncMock(return_value=True) 
        mock_app.api_client.delete_entries.return_value = {}
        trash_manager.load_data = AsyncMock()
        await trash_manager.action_empty_trash_only(None)
        mock_app.api_client.delete_entries.assert_called_with(["1", "2"], delete_forever=True)
        trash_manager.load_data.assert_called_once()