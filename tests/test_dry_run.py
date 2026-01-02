import pytest
from unittest.mock import MagicMock
from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager
class MockApp:
    def __init__(self):
        self.config_data = {'encryption_mode': 'standard', 'e2ee_password': 'test'}
        self.paths = MagicMock()
def test_dry_run_folder_creation_simulates_entry():
    app = MockApp()
    manager = MirrorUploadE2EEManager(app)
    manager._calculate_remote_path = lambda path, is_folder: path 
    manager.log_ui = MagicMock()
    cloud_tree = {"folders": {}, "files": {}}
    ws_id = "root_id"
    manager.handle_folder_creation("A/B", cloud_tree, ws_id, is_dry_run=True)
    assert "A" in cloud_tree["folders"]
    assert cloud_tree["folders"]["A"]["id"] == "SIMU_ID_A"
    assert "A/B" in cloud_tree["folders"]
    assert cloud_tree["folders"]["A/B"]["id"] == "SIMU_ID_A/B"
    assert manager.log_ui.call_count >= 2