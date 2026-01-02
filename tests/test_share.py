import pytest
import os
from unittest.mock import MagicMock, patch, ANY
from drimesyncunofficial.share import ShareManager
from drimesyncunofficial.constants import CONF_KEY_API_KEY

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {CONF_KEY_API_KEY: "dummy_key"}
    app.api_client = MagicMock()
    app.loop = MagicMock()
    app.is_mobile = False
    return app

@pytest.fixture
def share_manager(mock_app):
    return ShareManager(mock_app)

@pytest.mark.asyncio
async def test_generate_cloud_link_flow(share_manager):
    """Test the full flow of generating a cloud link."""
    # Setup UI mocks
    share_manager.input_file = MagicMock()
    share_manager.input_file.value = "test.txt"
    share_manager.share_switch = MagicMock(is_on=False) # Standard Mode
    share_manager.chk_pwd = MagicMock(value=False)
    share_manager.chk_expiration = MagicMock(value=False)
    share_manager.chk_notify = MagicMock(value=False)
    share_manager.chk_allow_download = MagicMock(value=True)
    
    # Mock internal methods
    share_manager.selected_file_path = "test.txt"
    share_manager._validate_password_compliance = MagicMock(return_value=True)
    
    # Mock Upload response (Centralized upload_file)
    mock_upload_resp = {"id": "123", "filename": "test.txt"}
    share_manager.app.api_client.upload_file.return_value = mock_upload_resp
    
    # Mock Link Gen response
    mock_link_resp = MagicMock(status_code=200)
    mock_link_resp.json.return_value = {"status": "success", "link": {"hash": "abc-def"}}
    share_manager.app.api_client.create_share_link.return_value = mock_link_resp
    
    # Verify execution
    with patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=1024), \
         patch("pathlib.Path.is_file", return_value=True):
        share_manager._generate_cloud_link_logic("password")
    
    # Verify Upload called
    share_manager.app.api_client.upload_file.assert_called_once()
    
    # Verify Link Creation
    share_manager.app.api_client.create_share_link.assert_called_with(
        "123", 
        password="password",
        expires_at=None,
        allow_edit=False,
        allow_download=True,
        notify_on_download=False
    )

def test_capsule_flow(share_manager):
    """Test the secure capsule flow logic."""
    share_manager.selected_file_path = "secret.pdf"
    share_manager.app.is_mobile = False
    
    # Mock CapsuleManager
    with patch("drimesyncunofficial.share.CapsuleManager") as MockCapsuleManager:
        with patch("pathlib.Path.is_dir", return_value=False), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", return_value=True):
             
            manager_instance = MockCapsuleManager.return_value
            manager_instance.create_capsule.return_value = "token123"
            
            # Mock Upload (Centralized upload_file)
            mock_upload_resp = {"id": "999"}
            share_manager.app.api_client.upload_file.return_value = mock_upload_resp
            
            mock_link_resp = MagicMock(status_code=200)
            mock_link_resp.json.return_value = {"status": "success", "link": {"hash": "capsule-hash"}}
            share_manager.app.api_client.create_share_link.return_value = mock_link_resp
            
            share_manager.chk_expiration = MagicMock(value=False)
            share_manager.chk_notify = MagicMock(value=True)
            
            # Execute (Simulate calling with Notify=True from UI)
            share_manager._generate_capsule_logic("StrongPass1!", notify=True)
            
            # Verify Capsule Creation
            manager_instance.create_capsule.assert_called_once()
            
            # Verify Upload
            share_manager.app.api_client.upload_file.assert_called_once()
            
            # Verify Link (Password should be None for capsule link, Notify should be True)
            share_manager.app.api_client.create_share_link.assert_called_with(
                "999", 
                password=None,
                expires_at=None,
                allow_edit=False,
                allow_download=True,
                notify_on_download=True
            )
