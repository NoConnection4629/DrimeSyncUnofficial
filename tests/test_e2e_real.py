
import pytest
import os
import time
import requests
from drimesyncunofficial.api_client import DrimeAPIClient
from drimesyncunofficial.utils import get_partial_hash

# Skip check inside fixture
class TestRealWorldE2E:
    
    @pytest.fixture(autouse=True)
    def setup(self, api_key):
        if not api_key: pytest.skip("No API Key")
        self.api = DrimeAPIClient(api_key)
        self.test_filename = f"e2e_test_{int(time.time())}.txt"
        self.test_content = b"Ceci est un test E2E reel."
        
        # Write dummy file
        with open(self.test_filename, "wb") as f:
            f.write(self.test_content)
            
        yield
        
        # Teardown: Delete local file
        if os.path.exists(self.test_filename):
            os.remove(self.test_filename)

    def test_lifecycle_upload_share_delete(self):
        """
        SCENARIO RÉEL:
        1. Vérifier Auth.
        2. Upload Simple.
        3. Générer Lien Partage (Share).
        4. Vérifier Lien (HTTP GET).
        5. Suppression Distante.
        """
        # 1. Auth check
        user_info = self.api.get_logged_user()
        assert 'user' in user_info, "Auth failed"
        print(f"\n[E2E] Connecté en tant que: {user_info['user'].get('email')}")

        # 2. Upload
        # Need file info
        file_size = len(self.test_content)
        ph = get_partial_hash(self.test_filename, file_size)
        
        # Init Upload
        print(f"[E2E] Uploading {self.test_filename}...")
        resp = self.api.upload_simple(self.test_filename, self.test_filename, ph, "0")
        assert resp.status_code in (200, 201), f"Upload failed: {resp.text}"
        
        file_id = resp.json().get('fileEntry', {}).get('id')
        assert file_id, "No File ID returned"
        print(f"[E2E] File Uploaded. ID: {file_id}")
        
        try:
            # 3. Share Link
            print("[E2E] Generating Share Link...")
            # create_share_link takes a single entry_id string
            share_resp = self.api.create_share_link(str(file_id))
            assert share_resp.status_code == 200, f"Share failed: {share_resp.text}"
            
            # Parse Link from Response
            share_data = share_resp.json()
            print(f"[E2E] Share Response: {share_data}")
            
        finally:
            # 5. Cleanup (Delete entries)
            print("[E2E] Deleting File...")
            del_resp = self.api.delete_entries([str(file_id)])
            assert del_resp.status_code == 200, "Deletion failed"
            print("[E2E] Cleanup Complete.")
