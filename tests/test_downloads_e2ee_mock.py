
import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
from drimesyncunofficial.downloads_workspace_e2ee import WorkspaceDownloadE2EEManager
from drimesyncunofficial.constants import CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD, MODE_E2EE_STANDARD

class TestDownloadsE2EEMock:
    
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.config_data = {
            CONF_KEY_ENCRYPTION_MODE: MODE_E2EE_STANDARD,
            CONF_KEY_E2EE_PASSWORD: "test_password"
        }
        app.api_client = MagicMock()
        app.loop = MagicMock()
        app.paths = MagicMock()
        return app

    @pytest.fixture
    def manager(self, mock_app):
        # Patch UI mixins and setup
        with patch('drimesyncunofficial.downloads_workspace_e2ee.derive_key', return_value=b"key123"), \
             patch('drimesyncunofficial.downloads_workspace_e2ee.generate_or_load_salt', return_value=b"salt"):
             
            mgr = WorkspaceDownloadE2EEManager(mock_app)
            mgr.e2ee_key = b"key123"
            mgr.log_ui = MagicMock() # Mock the mixin method directly
            mgr.lbl_progress = MagicMock()
            
            # Needed for _download_file_worker progress calculation
            mgr.total_size = 100
            mgr.total_downloaded_bytes = 0
            
            # Needed for _download_worker_bounded if tested (but here we test file worker)
            mgr.semaphore = MagicMock()
            
            return mgr

    def test_download_file_worker_success(self, manager):
        """Test successful download and decryption."""
        file_url = "http://fake.url/file.enc"
        save_path = "/tmp/downloads/file.txt"
        file_name = "file.txt"
        file_size = 100
        
        # Mock Response Context Manager
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"encrypted_chunk"]
        mock_response.headers = {'content-length': '100'}
        
        manager.app.api_client.get_download_stream.return_value.__enter__.return_value = mock_response

        # Mock File System and Decryption
        with patch("builtins.open", mock_open()) as mock_file, \
             patch("drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_file", return_value=b"decrypted_content") as mock_decrypt, \
             patch("tempfile.NamedTemporaryFile") as mock_temp, \
             patch("pathlib.Path.read_bytes", return_value=b"encrypted_chunk"), \
             patch("pathlib.Path.unlink"), \
             patch("os.makedirs"):
             
             # Setup Temp File Mock
             mock_temp_obj = MagicMock()
             mock_temp_obj.name = "/tmp/temp_enc"
             mock_temp.return_value.__enter__.return_value = mock_temp_obj
             
             # Execute
             success, msg, size = manager._download_file_worker(file_url, save_path, file_name, file_size)
             
             # Verify
             assert success is True
             assert msg == "OK"
             assert size == 100
             
             # Check Decryption called
             mock_decrypt.assert_called_with(b"encrypted_chunk", b"key123")
             
             # Check File Write (Final)
             handle = mock_file()
             handle.write.assert_any_call(b"decrypted_content")

    def test_download_file_worker_decrypt_failure(self, manager):
        """Test decryption failure handling."""
        file_url = "http://fake.url/bad.enc"
        save_path = "/tmp/downloads/bad.txt"
        
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"bad_chunk"]
        mock_response.headers = {'content-length': '100'}
        manager.app.api_client.get_download_stream.return_value.__enter__.return_value = mock_response

        with patch("builtins.open", mock_open()), \
             patch("drimesyncunofficial.downloads_manual_e2ee.E2EE_decrypt_file", return_value=None), \
             patch("tempfile.NamedTemporaryFile") as mock_temp, \
             patch("pathlib.Path.read_bytes", return_value=b"bad_chunk"), \
             patch("pathlib.Path.unlink"), \
             patch("os.makedirs"):
             
             # Setup Mock for NamedTemporaryFile
             mock_temp_file = MagicMock()
             mock_temp_file.name = "dummy_temp_path.enc"
             mock_temp.return_value.__enter__.return_value = mock_temp_file

             # Execute with patched paths
             with patch("os.path.exists", return_value=True), \
                  patch("os.unlink"):
                 success, msg, size = manager._download_file_worker(file_url, save_path, "bad.txt", 100)
             
             assert success is False
             assert "Erreur déchiffrement" in msg
