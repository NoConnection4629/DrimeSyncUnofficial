import pytest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import os
import json
import asyncio
from drimesyncunofficial.filigranage import WatermarkManager
from drimesyncunofficial.utils import MODE_NO_ENC
class TestFiligranage:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.paths.app = "/mock/app/path"
        app.config_data = {
            'api_key': 'fake_api_key',
            'encryption_mode': MODE_NO_ENC,
            'e2ee_password': 'test_password'
        }
        app.loop = MagicMock()
        app.loop.call_soon_threadsafe = lambda cb, *args: cb(*args)
        app.main_window.dialog = AsyncMock()
        return app
    @pytest.fixture
    def manager(self, mock_app):
        manager = WatermarkManager(mock_app)
        manager.window = MagicMock()
        manager.org_input = MagicMock()
        manager.motif_input = MagicMock()
        manager.auth_input = MagicMock()
        manager.ws_input = MagicMock()
        manager.chk_encrypt = MagicMock()
        manager.chk_parano = MagicMock()
        manager.pwd_input = MagicMock()
        manager.log_label = MagicMock()
        return manager
    def test_calculate_file_hash(self, manager):
        with patch("builtins.open", mock_open(read_data=b"test data")) as mock_file:
            expected_hash = "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
            assert manager.calculate_file_hash("dummy.txt") == expected_hash
    def test_get_secure_payload_valid(self, manager):
        async def run_test():
            manager.org_input.value = "Test Org"
            manager.auth_input.value = "Test Author"
            manager.chk_parano.value = False
            payload = await manager.get_secure_payload("fake_hash")
            assert payload["to"] == "TEST ORG"
            assert payload["doc_hash"] == "fake_hash"[:16]
            assert payload["author"] == "Test Author"
            assert payload["user_pwd"] is None
        asyncio.run(run_test())
    def test_get_secure_payload_parano_valid(self, manager):
        async def run_test():
            manager.org_input.value = "Test Org"
            manager.chk_parano.value = True
            manager.pwd_input.value = "secret123"
            payload = await manager.get_secure_payload("fake_hash")
            assert payload["user_pwd"] == "secret123"
        asyncio.run(run_test())
    @patch("drimesyncunofficial.filigranage.asyncio.run_coroutine_threadsafe")
    def test_omega_image_engine(self, mock_run_coro, manager):
        # Verify delegation to engine
        manager.engine = MagicMock()
        data = {
            "to": "TEST", "doc_hash": "hash123", "ts": "2023-01-01", 
            "uuid": "uuid123", "author": "Me"
        }
        qr_img = MagicMock()
        options = {"crypto_link": True, "microprint": True, "mesh": True, "anti_copy": False, "qr_triangulation": False}
        
        # We test that calling process_file delegates to engine.process_image for JPG
        with patch("os.path.exists", return_value=True):
            manager.process_file("input.jpg", data, options)
        
        manager.engine.generate_qr_code.assert_called_with(data)
        manager.engine.process_image.assert_called()
        args = manager.engine.process_image.call_args
        assert args[0][0] == "input.jpg"
        assert args[0][2] == data

    @patch("drimesyncunofficial.filigranage.asyncio.run_coroutine_threadsafe")
    def test_omega_pdf_engine(self, mock_run_coro, manager):
        # Verify delegation to engine
        manager.engine = MagicMock()
        data = {
            "to": "TEST", "doc_hash": "hash123", "ts": "2023-01-01", 
            "uuid": "uuid123", "author": "Me", "user_pwd": "pwd"
        }
        qr_img = MagicMock()
        options = {"crypto_link": True, "microprint": True, "mesh": True, "anti_copy": False, "qr_triangulation": False}
        
        # We test that calling process_file delegates to engine.process_pdf for PDF
        with patch("os.path.exists", return_value=True):
            manager.process_file("input.pdf", data, options)
            
        manager.engine.generate_qr_code.assert_called_with(data)
        manager.engine.process_pdf.assert_called()
        args = manager.engine.process_pdf.call_args
        assert args[0][0] == "input.pdf"
        assert args[0][2] == data
    def test_upload_file_success(self, manager):
        # Setup mock to return a valid file entry dict
        manager.app.api_client.upload_file.return_value = {'id': 'file_123', 'name': 'test.jpg'}
        
        with patch("os.path.getsize", return_value=1234):
            with patch("builtins.open", mock_open(read_data=b"content")):
                result = manager.upload_file("test.jpg", "ws_1")
        
        assert result is True
        # Verify api_client.upload_file was called with correct args
        manager.app.api_client.upload_file.assert_called_once()
        call_args = manager.app.api_client.upload_file.call_args
        assert call_args.kwargs['file_path'] == "test.jpg"
        assert call_args.kwargs['workspace_id'] == "ws_1"
        assert 'progress_callback' in call_args.kwargs

    def test_upload_file_failure_api_error(self, manager):
        # Setup mock to raise an exception
        manager.app.api_client.upload_file.side_effect = Exception("Network Error")
        
        with patch("os.path.getsize", return_value=1234):
            result = manager.upload_file("test.jpg", "ws_1")
            
        assert result is False

    def test_upload_file_failure_no_id(self, manager):
        # Setup mock to return empty dict or None (though api_client usually raises or returns valid)
        manager.app.api_client.upload_file.return_value = {}
        
        with patch("os.path.getsize", return_value=1234):
             result = manager.upload_file("test.jpg", "ws_1")
             
        assert result is False