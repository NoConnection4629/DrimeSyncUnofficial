import pytest
from unittest.mock import MagicMock, patch, ANY, call
import os
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config_data = {
        'api_key': 'test_key',
        'workers': 1,
        'semaphores': 1,
        'use_exclusions': True,
        'encryption_password': 'test_password'
    }
    app.paths = MagicMock()
    app.paths.data = MagicMock()
    app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
    app.api_client = MagicMock()
    return app

class TestReliability:

    @patch('drimesyncunofficial.uploads_mirror.asyncio.run_coroutine_threadsafe')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.get_local_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.load_local_cloud_tree')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.upload_file_router')
    @patch('drimesyncunofficial.uploads_mirror.MirrorUploadManager.save_local_cloud_tree')
    def test_mirror_resume_capability(self, mock_save, mock_upload, mock_load_cloud, mock_get_local, mock_asyncio, mock_app):
        """
        Reliability Test: Resume Logic.
        Simulates a restart where 50/100 files are already in cloud_tree.json.
        Verifies that only the remaining 50 are uploaded.
        """
        with patch('drimesyncunofficial.uploads_mirror.toga'):
            manager = MirrorUploadManager(mock_app)
            # Stub UI
            manager.log_ui = MagicMock()
            manager.update_status_ui = MagicMock()
            manager.btn_sync = MagicMock(); manager.box_secondary_btns = MagicMock()
            manager.btn_simu = MagicMock(); manager.btn_force = MagicMock(); manager.btn_pause = MagicMock(); manager.btn_cancel = MagicMock()
            manager.box_controls = MagicMock(); manager.lbl_warning_ws = MagicMock(); manager.lbl_conflict_warning = MagicMock()
            manager.selection_mirror_ws = MagicMock()

            # 100 Files on Disk
            files_disk = {f"file_{i}.txt": {"partial_hash": f"hash_{i}", "size": 10, "mtime": 10} for i in range(100)}
            mock_get_local.return_value = {"folders": set(), "files": files_disk}

            # 50 Files already in Cloud State (Synced)
            files_cloud = {f"file_{i}.txt": {"partial_hash": f"hash_{i}", "size": 10, "id": f"id_{i}"} for i in range(50)}
            mock_load_cloud.return_value = {"folders": {}, "files": files_cloud}

            # Mock successful upload for the rest
            mock_upload.return_value = {"id": "new_id", "size": 10}

            # Run Sync
            manager._thread_mirror_logic("/local", "0", is_dry_run=False, force_sync=False)

            # Verification
            # Should upload 50 files (range 50 to 99)
            assert mock_upload.call_count == 50, f"Resume failed! Uploaded {mock_upload.call_count} files instead of 50."
            
            # Verify we didn't upload file_0 (already done)
            # Check call args of upload_file_router
            uploaded_files = [c.args[1] for c in mock_upload.mock_calls] # arg 1 is cloud_relative_path (filename in this case)
            assert "file_0.txt" not in uploaded_files
            assert "file_99.txt" in uploaded_files

    @patch('drimesyncunofficial.uploads_mirror.time.sleep')
    @patch('drimesyncunofficial.uploads_mirror.asyncio.run_coroutine_threadsafe')
    def test_multipart_chunk_retry_logic(self, mock_asyncio, mock_sleep, mock_app):
        """
        Reliability Test: Multipart Chunk Retry.
        Simulates a chunk upload failing 2 times then succeeding.
        Verifies `upload_multipart` retries the chunk.
        """
        with patch('drimesyncunofficial.uploads_mirror.toga'), \
             patch('drimesyncunofficial.uploads_mirror.open', new_callable=MagicMock) as mock_open:
            
            manager = MirrorUploadManager(mock_app)
            manager.log_ui = MagicMock()
            manager.stop_event = MagicMock(); manager.stop_event.is_set.return_value = False
            manager.is_paused = False

            # Setup params
            local_info = {"full_path": "big_file.iso", "size": 50*1024*1024, "mtime": 10, "partial_hash": "h"}
            
            # Mocks for API flow
            # 1. Init
            mock_app.api_client.upload_multipart_init.return_value = MagicMock(status_code=200, json=lambda: {"uploadId": "uid", "key": "key"})
            # 2. Sign
            mock_app.api_client.upload_multipart_sign_batch.return_value = MagicMock(status_code=200, json=lambda: {"urls": [{"partNumber": 1, "url": "http://upload"}]})
            
            # 3. Put Chunk - FAIL twice, then SUCCEED
            # We need to mock the response object
            fail_resp = MagicMock(status_code=500, headers={})
            success_resp = MagicMock(status_code=200, headers={"ETag": '"etag"'})
            
            mock_app.api_client.upload_multipart_put_chunk.side_effect = [fail_resp, fail_resp, success_resp]
            
            # 4. Complete
            mock_app.api_client.upload_multipart_complete.return_value = MagicMock(status_code=200)
            # 5. Create Entry
            mock_app.api_client.create_entry.return_value = MagicMock(status_code=200, json=lambda: {"fileEntry": {"id": "final_id"}})

            # Mock file read
            mock_file_handle = mock_open.return_value.__enter__.return_value
            # Read returns data once (chunk), then empty (EOF)
            mock_file_handle.read.side_effect = [b'data', b''] 

            # Run
            # We force upload_multipart to be called by upload_file_router, or call it directly.
            # Call directly to test the logic in isolation.
            res = manager.upload_multipart(local_info, "remote/big_file.iso", "key", "0", "thread")

            # Verification
            # Should succeed
            assert res is not None
            assert res['id'] == "final_id"
            
            # Check Put Chunk calls
            # Should be 3 calls (Fail, Fail, Success)
            assert mock_app.api_client.upload_multipart_put_chunk.call_count == 3

            
    @patch('drimesyncunofficial.uploads_mirror_e2ee.toga')
    @patch('drimesyncunofficial.uploads_mirror_e2ee.E2EE_encrypt_file')
    def test_e2ee_lifecycle_integrity(self, mock_encrypt, mock_toga, mock_app):
        """
        Reliability Test: E2EE Lifecycle.
        Verifies that files are encrypted before upload and temp files are cleaned up.
        """
        # Needed to mock salt loading/key derivation which happens in __init__ or show
        with patch('drimesyncunofficial.uploads_mirror_e2ee.generate_or_load_salt', return_value=b'salt'), \
             patch('drimesyncunofficial.uploads_mirror_e2ee.derive_key', return_value=b'key'), \
             patch('drimesyncunofficial.uploads_mirror_e2ee.MirrorUploadE2EEManager._show_error_dialog_async'), \
             patch('drimesyncunofficial.uploads_mirror_e2ee.tempfile.NamedTemporaryFile') as mock_temp:
            
            manager = MirrorUploadE2EEManager(mock_app)
            manager.e2ee_key = b'key'
            manager.log_ui = MagicMock()
            
            # Mock Temp File
            mock_temp_obj = MagicMock()
            mock_temp_obj.name = "temp_encrypted.bin"
            mock_temp.return_value.__enter__.return_value = mock_temp_obj
            
            # Mock API upload
            mock_app.api_client.upload_simple.return_value = MagicMock(status_code=200, json=lambda: {"fileEntry": {"id": "enc_id"}})
            
            # Call upload_simple_e2ee directly
            local_info = {"full_path": "secret.txt", "size": 100, "mtime": 100, "partial_hash": "h"}
            
            with patch('drimesyncunofficial.uploads_mirror_e2ee.Path') as mock_path:
                mock_path.return_value.name = "secret.txt.enc"
                
                result = manager.upload_simple_e2ee(local_info, "remote/secret.txt.enc", "key", "0", "thread")
                
                # Check Encryption called
                mock_encrypt.assert_called_with("secret.txt", b'key')
                
                # Check Upload called with temp file
                mock_app.api_client.upload_simple.assert_called()
                args = mock_app.api_client.upload_simple.call_args
                assert args[0][0] == "temp_encrypted.bin"
                
                # Check Temp file deletion (unlink)
                # We mock Path(tmp_path).unlink
                # Just verifying cleanup logic is present
                assert mock_path("temp_encrypted.bin").unlink.called or mock_path.return_value.unlink.called
                
                assert result["id"] == "enc_id"
