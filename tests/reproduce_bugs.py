import sys
import os
from unittest.mock import MagicMock, patch
sys.modules['toga'] = MagicMock()
sys.modules['toga.style'] = MagicMock()
sys.modules['toga.style.pack'] = MagicMock()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import unittest
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
from drimesyncunofficial.configuration import ConfigManager
class TestBugReproduction(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.config_data = {
            'folder_standard_path': '/tmp',
            'workspace_standard_id': '0',
            'api_key': 'test',
            'workers': 5,
            'semaphores': 5,
            'debug_mode': False,
            'use_exclusions': True
        }
        self.mock_app.paths.data = MagicMock()
    def test_mirror_dry_run_key_error(self):
        print("\n--- Testing Mirror Dry Run KeyError ---")
        manager = MirrorUploadManager(self.mock_app)
        cloud_tree = {"folders": {}, "files": {}}
        workspace_id = "0"
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
sys.modules['toga'] = MagicMock()
sys.modules['toga.style'] = MagicMock()
sys.modules['toga.style.pack'] = MagicMock()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import unittest
from drimesyncunofficial.uploads_mirror import MirrorUploadManager
from drimesyncunofficial.configuration import ConfigManager
class TestBugReproduction(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.config_data = {
            'folder_standard_path': '/tmp',
            'workspace_standard_id': '0',
            'api_key': 'test',
            'workers': 5,
            'semaphores': 5,
            'debug_mode': False,
            'use_exclusions': True
        }
        self.mock_app.paths.data = MagicMock()
    def test_mirror_dry_run_key_error(self):
        print("\n--- Testing Mirror Dry Run KeyError ---")
        manager = MirrorUploadManager(self.mock_app)
        cloud_tree = {"folders": {}, "files": {}}
        workspace_id = "0"
        try:
            manager.handle_folder_creation("folder1", cloud_tree, workspace_id, is_dry_run=True)
            manager.handle_folder_creation("folder1/subfolder", cloud_tree, workspace_id, is_dry_run=True)
            print("Mirror Dry Run: Success (No KeyError)")
        except KeyError as e:
            self.fail(f"Mirror Dry Run Failed: Caught KeyError: {e}")
    def test_config_type_error(self):
        print("\n--- Testing Config TypeError (Fixed) ---")
        app = MagicMock()
        app.config_data = {}
        app.config_path = "config.json" 
        async def async_mock(*args, **kwargs): pass
        app.verify_api_startup = async_mock
        with patch("builtins.open", mock_open()):
            with patch("json.dump"):
                config = ConfigManager(app)
                config.window = MagicMock()
                config.input_workers = MagicMock()
                config.input_workers.value = None
                config.input_semaphores = MagicMock()
                config.input_semaphores.value = None
                config.chk_debug = MagicMock()
                config.chk_exclusions = MagicMock()
                try:
                    import asyncio
                    asyncio.run(config.save_config_action(None))
                    print("Config Save: Success (No TypeError)")
                except TypeError as e:
                    self.fail(f"Config Save Failed: Caught TypeError: {e}")
                except Exception as e:
                    self.fail(f"Config Save Failed: Caught Exception: {e}")
if __name__ == '__main__':
    unittest.main()