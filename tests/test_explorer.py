import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from drimesyncunofficial.explorer import ExplorerManager
class TestExplorerManager:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.config_data = {'api_key': 'fake_key', 'workspace_standard_id': '0'}
        app.workspace_list_cache = [{'id': 1, 'name': 'Work'}]
        app.is_mobile = False
        app.api_client = MagicMock() 
        app.main_window = MagicMock()
        app.main_window.dialog = AsyncMock()
        return app
    @pytest.fixture
    def explorer_manager(self, mock_app):
        with patch('toga.Window'), patch('toga.Box'), patch('toga.Label'), \
             patch('toga.Button'), patch('toga.Selection'), patch('toga.DetailedList'), \
             patch('toga.Table'), patch('toga.Icon'), patch('toga.Switch'):
            manager = ExplorerManager(mock_app)
            manager.selection_ws = MagicMock()
            manager.selection_ws.value = "Espace Personnel (ID: 0)"
            manager.status = MagicMock()
            manager.table = MagicMock()
            manager.table.data = []
            manager.list = MagicMock()
            manager.chk_show_decrypted = MagicMock()
            manager.chk_show_decrypted.value = False
            return manager
    @pytest.mark.asyncio
    async def test_load_data_root(self, explorer_manager, mock_app):
        mock_data = {
            "data": [
                {"id": 10, "name": "file.txt", "size": 500, "updated_at": "2023-01-01T10:00:00", "type": "file"},
                {"id": 11, "name": "docs", "size": 0, "updated_at": "2023-01-02T10:00:00", "type": "folder"}
            ]
        }
        mock_app.api_client.list_files.return_value = mock_data
        await explorer_manager.load_data()
        assert len(explorer_manager.files_cache) == 2
        assert explorer_manager.files_cache[1]['name'] == "docs"
        mock_app.api_client.list_files.assert_called_with({"deletedOnly": 0, "workspaceId": "0"})
    @pytest.mark.asyncio
    async def test_load_data_with_folder(self, explorer_manager, mock_app):
        explorer_manager.current_folder_id = "999"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_app.api_client.list_files.return_value = mock_response
        await explorer_manager.load_data()
        mock_app.api_client.list_files.assert_called_with({"deletedOnly": 0, "workspaceId": "0", "folderId": "999"})
    @pytest.mark.asyncio
    async def test_enter_folder(self, explorer_manager, mock_app):
        explorer_manager.files_cache = [
            {"id": 50, "name": "my_folder", "type": "folder"}
        ]
        explorer_manager.refresh = MagicMock()
        explorer_manager._enter_folder("50")
        assert explorer_manager.current_folder_id == "50"
        assert explorer_manager.history == [None] 
        explorer_manager.refresh.assert_called_once()
    @pytest.mark.asyncio
    async def test_action_up(self, explorer_manager):
        explorer_manager.history = [None, "123"]
        explorer_manager.current_folder_id = "456"
        explorer_manager.refresh = MagicMock()
        explorer_manager.action_up(None)
        assert explorer_manager.current_folder_id == "123"
        assert explorer_manager.history == [None]
        explorer_manager.refresh.assert_called_once()
    @pytest.mark.asyncio
    async def test_action_up_at_root(self, explorer_manager):
        explorer_manager.history = []
        explorer_manager.current_folder_id = None
        explorer_manager.refresh = MagicMock()
        explorer_manager.action_up(None)
        assert explorer_manager.current_folder_id is None
        explorer_manager.refresh.assert_not_called()
    @pytest.mark.asyncio
    async def test_action_soft_delete(self, explorer_manager, mock_app):
        selected_file = {"id": 10, "name": "delete_me.txt"}
        explorer_manager.get_selection_list = MagicMock(return_value=[selected_file])
        explorer_manager.window = MagicMock()
        explorer_manager.window.dialog = AsyncMock(return_value=True) 
        mock_app.api_client.delete_entries.return_value = {}
        explorer_manager.refresh = MagicMock()
        await explorer_manager.action_soft_delete(None)
        mock_app.api_client.delete_entries.assert_called_with(["10"], delete_forever=False)
        explorer_manager.refresh.assert_called_once()
    @pytest.mark.asyncio
    async def test_action_rename(self, explorer_manager, mock_app):
        selected_file = {"id": 10, "name": "old_name.txt"}
        explorer_manager.get_selection_list = MagicMock(return_value=[selected_file])
        explorer_manager._ask_text_dialog = AsyncMock(return_value="new_name.txt")
        mock_app.api_client.rename_entry.return_value = {"success": True}
        explorer_manager.refresh = MagicMock()
        await explorer_manager.action_rename(None)
        mock_app.api_client.rename_entry.assert_called_with(10, "new_name.txt")
        explorer_manager.refresh.assert_called_once()
    @pytest.mark.asyncio
    async def test_load_data_decryption(self, explorer_manager, mock_app):
        explorer_manager.chk_show_decrypted.value = True
        mock_data = {"data": [
            {"id": 1, "name": "encrypted_base.txt", "size": 100, "type": "file", "updated_at": "2023-01-01"}, 
            {"id": 2, "name": "encrypted_full.enc", "size": 200, "type": "file", "updated_at": "2023-01-01"}, 
            {"id": 3, "name": "plain.txt", "size": 300, "type": "file", "updated_at": "2023-01-01"} 
        ]}
        mock_app.api_client.list_files.return_value = mock_data
        def decrypt_side_effect(name, key):
            if name == "encrypted_base": return "decrypted_base"
            if name == "encrypted_full": return "decrypted_full"
            return name
        with patch('drimesyncunofficial.explorer.get_secure_secret', return_value="password"), \
             patch('drimesyncunofficial.explorer.generate_or_load_salt', return_value=b'salt'), \
             patch('drimesyncunofficial.explorer.derive_key', return_value=b'key'), \
             patch('drimesyncunofficial.explorer.E2EE_decrypt_name', side_effect=decrypt_side_effect):
            await explorer_manager.load_data()
            assert explorer_manager.table.data[0]['nom'] == "📄 decrypted_base.txt"
            assert explorer_manager.table.data[1]['nom'] == "📄 decrypted_full"
            assert explorer_manager.table.data[2]['nom'] == "📄 plain.txt"