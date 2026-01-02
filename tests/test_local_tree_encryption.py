import os
import json
import pytest
from unittest.mock import MagicMock
from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager
from drimesyncunofficial.utils import derive_key, E2EE_decrypt_bytes
@pytest.fixture
def mock_app(tmp_path):
    app = MagicMock()
    app.paths.data = tmp_path
    app.config_data = {'encryption_mode': 'E2EE_STANDARD', 'e2ee_password': 'testpassword'}
    return app
def test_local_tree_encryption_workflow(mock_app, tmp_path):
    manager = MirrorUploadE2EEManager(mock_app)
    salt = os.urandom(16)
    manager.e2ee_key = derive_key("testpassword", salt)
    tree = {"folders": ["test_folder"], "files": {"test.txt": {"size": 123}}}
    state_dir = tmp_path / "MirrorStates" / "Test_0_E2EE"
    state_dir.mkdir(parents=True, exist_ok=True)
    manager.save_local_cloud_tree(tree, str(state_dir), encrypt=True)
    file_path = state_dir / "00_drime_cloud_tree.json"
    assert file_path.exists()
    with open(file_path, 'rb') as f:
        content = f.read()
        with pytest.raises(Exception):
            json.loads(content)
    decrypted = E2EE_decrypt_bytes(content, manager.e2ee_key)
    assert decrypted is not None
    loaded_json = json.loads(decrypted)
    assert loaded_json == tree
    loaded_tree = manager.load_local_cloud_tree(str(state_dir), "fake_api_key", "0")
    assert loaded_tree == tree
    with open(file_path, 'w') as f:
        json.dump(tree, f)
    loaded_tree_clear = manager.load_local_cloud_tree(str(state_dir), "fake_api_key", "0")
    assert loaded_tree_clear == tree
    manager.save_local_cloud_tree(tree, str(state_dir), encrypt=False)
    with open(file_path, 'r') as f:
        content_clear = json.load(f)
    assert content_clear == tree