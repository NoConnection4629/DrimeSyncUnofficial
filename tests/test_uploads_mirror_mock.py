
import pytest
from unittest.mock import MagicMock, patch, ANY, mock_open
import os
from pathlib import Path
from drimesyncunofficial.uploads_mirror import MirrorUploadManager

class TestMirrorUploadsMock:
    
    @pytest.fixture
    def manager(self):
        app = MagicMock()
        app.paths.data = Path("/fake/data")
        app.config_data = {}
        manager = MirrorUploadManager(app)
        manager.log_ui = MagicMock()
        return manager

    def test_get_local_tree_structure(self, manager):
        """Test recursive scanning and exclusion logic using a real temp directory."""
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            
            # Create structure
            # /root
            #   - file1.txt
            #   - subdir/
            #       - file2.jpg
            #   - excluded_dir/
            #       - junk.txt
            #   - test.tmp (excluded by pattern)
            
            (root / "file1.txt").write_text("content1")
            (root / "subdir").mkdir()
            (root / "subdir" / "file2.jpg").write_text("image")
            (root / "excluded_dir").mkdir()
            (root / "excluded_dir" / "junk.txt").write_text("junk")
            (root / "test.tmp").write_text("temp")
            
            # Mock get_partial_hash to always work
            manager.get_partial_hash = MagicMock(return_value="hash123")
            
            # We must NOT mock Path or os.walk here, as we rely on real FS.
            # We ONLY mock load_exclusion_patterns.
            
            with patch("drimesyncunofficial.uploads_mirror.load_exclusion_patterns", return_value=["excluded_dir", "*.tmp", "excluded_dir/*"]):
                tree = manager.get_local_tree(str(root), "fake_state_dir", use_exclusions=True)
            
            # Verify Files
            # "file1.txt" -> OK
            # "subdir/file2.jpg" -> OK
            # "excluded_dir/junk.txt" -> Should be missing
            # "test.tmp" -> Should be missing
            
            files = tree["files"]
            assert "file1.txt" in files
            assert "subdir/file2.jpg" in files
            assert "test.tmp" not in files
            # Note: "excluded_dir/junk.txt" might be excluded if we exclude the folder "excluded_dir" in os.walk logic
            # Logic: if d in exclusions -> dirs.remove(d). 
            # So "excluded_dir" should be removed from traversal.
            
            # Check keys to be sure
            keys = list(files.keys())
            assert "excluded_dir/junk.txt" not in keys
            assert len(files) == 2
            
            # Verify Folders
            folders = tree["folders"]
            assert "subdir" in folders
            assert "excluded_dir" not in folders 

    def test_handle_folder_creation(self, manager):
        """Test recursive folder creation logic."""
        cloud_tree = {"folders": {"existing": {"id": "1"}}}
        ws_id = "0"
        
        # Scenario: create "existing/new"
        # Parent "existing" exists.
        
        # Mock API
        # create_folder returns a dict (parsed JSON), not a Response object
        manager.app.api_client.create_folder.return_value = {"id": "new_id"}
        
        manager.handle_folder_creation("existing/new", cloud_tree, ws_id, False)
        
        assert "existing/new" in cloud_tree["folders"]
        assert cloud_tree["folders"]["existing/new"]["id"] == "new_id"
        
        # Verify call arguments
        # parent_id should be "1" (from existing)
        manager.app.api_client.create_folder.assert_called_with(name="new", parent_id="1", workspace_id="0")

    def test_upload_worker_flow(self, manager):
        """Test worker picks task and calls router."""
        q = MagicMock()
        res_q = MagicMock()
        
        # Item: (rel_path, info_dict)
        item = ("folder/file.txt", {"size": 100})
        
        # q.get_nowait side effect: return item once, then raise Empty or throw exception to break loop
        q.get_nowait.side_effect = [item, Exception("Empty")]
        
        with patch.object(manager, "upload_file_router", return_value={"id": "uploaded"}) as mock_router:
            manager.upload_worker(q, res_q, "key", "ws1")
            
            mock_router.assert_called_once()
            args = mock_router.call_args
            assert args[0][0] == item[1] # info
            # remote path logic mocked? "folder/file.txt" -> "folder/file.txt" (if no renames)
            
            # Check Result Queue
            res_q.put.assert_called_with(("folder/file.txt", {"id": "uploaded"}))

