import unittest
import os
import shutil
import json
import base64
from pathlib import Path
from drimesyncunofficial.capsule_manager import CapsuleManager

class TestCapsuleManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("tests_temp_capsule")
        self.test_dir.mkdir(exist_ok=True)
        self.manager = CapsuleManager()

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except:
            pass

    def test_generate_human_salt(self):
        salt = self.manager.generate_human_salt()
        self.assertIsInstance(salt, str)
        # Format XXXX-XXXX-XXXX-XXXX = 16 chars + 3 dashes = 19 chars
        self.assertEqual(len(salt), 19) 
        self.assertEqual(salt.count('-'), 3)

    def test_compress_folder(self):
        # Create dummy folder structure
        src = self.test_dir / "folder_to_zip"
        src.mkdir()
        (src / "test.txt").write_text("hello world", encoding="utf-8")
        
        output_zip = self.test_dir / "output.zip"
        result = self.manager.compress_folder(src, output_zip)
        
        self.assertTrue(result)
        self.assertTrue(output_zip.exists())
        self.assertGreater(output_zip.stat().st_size, 0)

    def test_create_capsule(self):
        # Create dummy file
        src_file = self.test_dir / "secret.txt"
        src_file.write_text("This is a secret message", encoding="utf-8")
        
        output_html = self.test_dir / "capsule_output.html"
        password = "strongpassword123"
        
        token = self.manager.create_capsule(src_file, output_html, password)
        
        self.assertIsNotNone(token)
        self.assertTrue(output_html.exists())
        
        content = output_html.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        # The placeholders should have been replaced
        self.assertNotIn("__PAYLOAD__", content) 
        self.assertNotIn("__IV__", content)
        self.assertIn("AES-256-GCM", content)
        
        # We can't easily decrypt in Python without duplicating logic, 
        # but we verified the structure generation.

if __name__ == '__main__':
    unittest.main()
