
import pytest
import asyncio
import threading
import time
from unittest.mock import MagicMock, patch, ANY
from drimesyncunofficial.share import ShareManager
from drimesyncunofficial.filigranage import WatermarkManager
from drimesyncunofficial.mixins import LoggerMixin

# --- FIXTURES ---
@pytest.fixture
def mock_app_extreme():
    app = MagicMock()
    app.config_data = {
        'api_key': 'test_key',
        'debug_mode': True
    }
    app.loop.call_soon_threadsafe = MagicMock(side_effect=lambda f, *args: f(*args))
    app.api_client = MagicMock()
    app.paths = MagicMock()
    return app

# --- EXTREME TESTS ---

class TestExtremeResilience:

    @patch('drimesyncunofficial.share.toga')
    def test_share_api_chaos_monkey(self, mock_toga, mock_app_extreme):
        """
        CHAOS TEST: ShareManager vs API Errors.
        Simulates: Timeout, 500 Internal Error, Garbage JSON, 403 Forbidden.
        Verifies: No crash, proper error logging.
        """
        manager = ShareManager(mock_app_extreme)
        manager.log_ui = MagicMock()
        manager.selected_file_path = "test.txt"
        
        # Mocks
        manager.chk_link_pwd = MagicMock(value=False)
        manager.chk_download = MagicMock(value=True)
        manager.chk_expiration = MagicMock(value=False)
        manager.chk_notify = MagicMock(value=False)
        manager.chk_edit = MagicMock(value=False)
        manager.switch_secure = MagicMock(value=False)
        
        # 1. Simulate Upload Success
        manager._smart_upload = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"id": "123"}))
        
        # 2. Chaos on Link Generation
        # Case A: Timeout (ConnectionError)
        mock_app_extreme.api_client.create_share_link.side_effect = ConnectionError("Timeout!")
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=100):
             manager._generate_cloud_link_logic()
        
        manager.log_ui.assert_called_with(ANY, ANY) # Should log error
        assert "Timeout!" in str(manager.log_ui.call_args_list[-1])

        # Case B: 500 Internal Server Error
        mock_app_extreme.api_client.create_share_link.side_effect = None
        mock_app_extreme.api_client.create_share_link.return_value = MagicMock(status_code=500, text="Internal Explode")
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=100):
             manager._generate_cloud_link_logic()
        
        manager.log_ui.assert_called_with(ANY, ANY)
        
        # Case C: Garbage JSON Response
        mock_app_extreme.api_client.create_share_link.return_value = MagicMock(status_code=200, json=lambda: 1/0) # Raises ZeroDivision logic
        # OR just invalid json text
        mock_app_extreme.api_client.create_share_link.return_value = MagicMock(status_code=200)
        mock_app_extreme.api_client.create_share_link.return_value.json.side_effect = ValueError("Invalid JSON")
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=100):
             manager._generate_cloud_link_logic()
        
        # Should catch exception and log it
        manager.log_ui.assert_called()

    @patch('drimesyncunofficial.filigranage.toga')
    @patch('drimesyncunofficial.filigranage.asyncio.run_coroutine_threadsafe')
    def test_watermark_path_fuzzing(self, mock_asyncio_run, mock_toga, mock_app_extreme):
        """
        FUZZING TEST: WatermarkManager vs Weird Paths.
        Simulates: Paths with Emojis, Spaces, Special Chars.
        """
        manager = WatermarkManager(mock_app_extreme)
        manager.log_ui = MagicMock()
        manager.org_input = MagicMock(value="Org")
        manager.motif_input = MagicMock(value="Motif")
        manager.auth_input = MagicMock(value="Auth with 🚀")
        manager.ws_input = MagicMock(value="Mode Local")
        
        manager.chk_crypto_link = MagicMock(value=False)
        manager.chk_microprint = MagicMock(value=False)
        manager.chk_anti_copy = MagicMock(value=False)
        manager.chk_qr_triangulation = MagicMock(value=False)
        manager.chk_parano = MagicMock(value=False)
        manager.chk_encrypt = MagicMock(value=False)

        # Weird Path
        weird_path = "C:/Users/Test/Dossier 📁/Ima'ge [1] #Strange!.jpg"
        
        # Mock Image Engine to avoid actual processing but verify path handling
        manager.engine = MagicMock()
        manager.engine.process_image = MagicMock()
        manager.engine.generate_qr_code = MagicMock()
        manager.calculate_file_hash = MagicMock(return_value="hash")
        
        # Run
        # We need to mock os.path.exists checks inside run_omega or process_file
        # process_file calls os.path.exists at the end.
        with patch('threading.Thread') as mock_thread: 
            # Bypass thread start to run sync
            mock_thread.return_value.start.side_effect = lambda: manager.process_file(weird_path, {"to":"Org", "doc_hash":"h", "ts":"t", "uuid":"u"}, {})
            
            with patch('os.path.exists', return_value=True), \
                 patch('builtins.open', new_callable=MagicMock):
                 
                manager._continue_omega_process(weird_path) 

        # Let's test process_file directly which is the target of the thread
        data = {"to": "TEST", "doc_hash": "ABC", "ts": "NOW", "uuid": "123"}
        options = {}
        
        with patch('os.path.exists', return_value=True): # Pretend output exists
             manager.process_file(weird_path, data, options)
        
        # Verify engine called with weird path
        manager.engine.process_image.assert_called()
        args = manager.engine.process_image.call_args
        assert args[0][0] == weird_path # Input passed correctly
        # Verify output path construction handles weird chars
        out_path = args[0][1]
        assert "Ima'ge [1] #Strange!_SECURE.jpg" in out_path

    @patch('drimesyncunofficial.mixins.update_logs_threadsafe')
    def test_threading_stress_logger(self, mock_update, mock_app_extreme):
        """
        STRESS TEST: 20 Threads logging simultaneously.
        Verifies: No Deadlock, All logs processed (mock called correct number of times).
        """
        class Stresser(LoggerMixin):
            def __init__(self, app): self.app = app
            
        obj = Stresser(mock_app_extreme)
        
        NUM_THREADS = 20
        LOGS_PER_THREAD = 50
        
        def worker(tid):
            for i in range(LOGS_PER_THREAD):
                obj.log_ui(f"T{tid}-Msg{i}")
                # Small sleep to force context switches
                # time.sleep(0.0001) 
        
        threads = []
        for i in range(NUM_THREADS):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # Verify total calls
        total_logs = NUM_THREADS * LOGS_PER_THREAD
        assert mock_update.call_count == total_logs
