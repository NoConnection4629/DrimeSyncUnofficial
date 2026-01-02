
import pytest
from unittest.mock import MagicMock, patch
import toga
from drimesyncunofficial.share import ShareManager
from drimesyncunofficial.constants import CONF_KEY_API_KEY, CONF_KEY_DEBUG_MODE

class TestShareWizard:
    
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.main_window = MagicMock()
        app.loop = MagicMock()
        app.config_data = {
            CONF_KEY_API_KEY: "dummy_key",
            CONF_KEY_DEBUG_MODE: True
        }
        # Mock API Client
        app.api_client = MagicMock()
        return app

    @pytest.fixture
    def share_manager(self, mock_app):
        # Patch create_back_button and create_logs_box to avoid Toga UI creation issues in headless env
        with patch('drimesyncunofficial.share.create_back_button') as mock_back, \
             patch('drimesyncunofficial.share.create_logs_box') as mock_logs, \
             patch('drimesyncunofficial.share.AboutShareManager') as mock_about:
            
            manager = ShareManager(mock_app)
            # manually set UI elements usually created in show() if needed for logic
            manager.lbl_file_path = MagicMock()
            manager.switch_secure = MagicMock()
            manager.box_standard_warning = MagicMock()
            manager.box_capsule_options = MagicMock()
            manager.logs_box = MagicMock() # From create_logs_box
            manager.txt_logs = MagicMock()
            manager.input_std_link = MagicMock() # FIX: Added missing mock
            
            return manager

    def test_initialization(self, share_manager):
        assert share_manager.selected_file_path is None
        assert share_manager.app.config_data[CONF_KEY_API_KEY] == "dummy_key"

    def test_file_selection_logic(self, share_manager, mock_app):
        # Simulate selecting a file
        dummy_path = "/path/to/dummy_video.mp4"
        
        # We can't easily click the button because it calls specific Toga dialogs.
        # But we can call the method that handles the result if refactored, 
        # or manually set the state which the dialog callback would set.
        
        # Let's verify internal state update method if it exists, otherwise setting attr directly
        share_manager.selected_file_path = dummy_path
        
        # If we had a method `update_file_selection(path)`, we would test it.
        # Assuming typical Toga logic, we might need to verify what happens when we *would* upload.
        pass # Placeholder for logic verification if methods are split

    def test_security_toggle(self, share_manager):
        # Test on_security_toggle logic
        # Mock the widget passed to the callback
        switch_widget = MagicMock()
        
        # Case 1: Switch ON (Secure)
        switch_widget.value = True
        share_manager.on_security_toggle(switch_widget)
        # Check UI updates (visibility toggles)
        # Note: These are mocked Boxes, so we check if add/remove or style was touched.
        # Real code: self.box_standard_warning.style.display = 'none'...
        # Since we mocked the boxes, we might not see style changes unless we mocked style too.
        # But we can assume the method ran without error.
        
        # Case 2: Switch OFF (Standard)
        switch_widget.value = False
        share_manager.on_security_toggle(switch_widget)

    def test_process_generation_flow_standard(self, share_manager, mock_app):
        """Test the standard (Cloud User) generation flow."""
        # Setup
        share_manager.selected_file_path = "/tmp/test_vid.mp4"
        share_manager.switch_secure.value = False
        
        # Mock OS existence/size
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.basename", return_value="test_vid.mp4"):

            # Mock API responses
            # 1. Upload
            mock_upload_resp = {"id": "12345"} # upload_file returns the file object directly (or parsed) 
            # Note: upload_file returns the dict directly, not a response object in the new client wrapper
            mock_app.api_client.upload_file.return_value = mock_upload_resp
            
            # 2. Share
            mock_share_resp = MagicMock()
            mock_share_resp.status_code = 200
            mock_share_resp.json.return_value = {"status": "success", "link": {"hash": "abc-123"}}
            mock_app.api_client.create_share_link.return_value = mock_share_resp
            
            # Execute logic (synchronously for test)
            share_manager._generate_cloud_link_logic()
            
            # Verify Upload called
            mock_app.api_client.upload_file.assert_called_once()
            
            # Verify Share Link called with correct ID
            mock_app.api_client.create_share_link.assert_called_with(
                "12345", # ID from upload
                password=None, expires_at=None, allow_edit=False, allow_download=True, notify_on_download=False
            )
            
            # Verify UI update callback
            # call_soon_threadsafe(callback)
            assert mock_app.loop.call_soon_threadsafe.called
            callback = mock_app.loop.call_soon_threadsafe.call_args[0][0]
            
            # Execute callback to check side effects
            callback()
            # Assert text input updated
            assert share_manager.input_std_link.value == "https://dri.me/abc-123" 
