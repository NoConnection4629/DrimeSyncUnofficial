import pytest
from drimesyncunofficial.utils import format_size, format_display_date, get_partial_hash, get_total_size, make_zip, sanitize_filename_for_upload, restore_filename_from_download
import os
import tempfile
class TestUtils:
    def test_format_size(self):
        assert format_size(0) == "0 o"
        assert format_size(100) == "100 o"
        assert format_size(1024) == "1.00 Ko"
        assert format_size(1024 * 1024) == "1.00 Mo"
        assert format_size(1024 * 1024 * 1024) == "1.00 Go"
        assert format_size(None) == "0 o"
        assert format_size("invalid") == "0 o"
    def test_format_display_date(self):
        assert format_display_date("2023-10-27T10:00:00") == "27/10/2023 10:00"
        assert format_display_date("2023-10-27T10:00:00.123Z") == "27/10/2023 10:00"
        assert format_display_date(None) == "-"
        assert format_display_date("invalid-date") == "invalid-date"
    def test_get_partial_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"a" * 10000)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "wb") as f:
                f.write(b"small content")
            file_size = os.path.getsize(tmp_path)
            hash_val = get_partial_hash(tmp_path, file_size)
            assert hash_val is not None
            with open(tmp_path, "wb") as f:
                f.write(b"a" * 10000)
            file_size = os.path.getsize(tmp_path)
            hash_val_large = get_partial_hash(tmp_path, file_size)
            assert hash_val_large is not None
            assert hash_val != hash_val_large
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    def test_get_partial_hash_nonexistent(self):
        assert get_partial_hash("nonexistent_file", 100) is None

    def test_get_total_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "f1.txt")
            with open(f1, "wb") as f: f.write(b"a" * 10)
            d1 = os.path.join(tmpdir, "sub")
            os.mkdir(d1)
            f2 = os.path.join(d1, "f2.txt")
            with open(f2, "wb") as f: f.write(b"b" * 20)
            
            assert get_total_size(f1) == 10
            assert get_total_size(tmpdir) == 30
            assert get_total_size("nonexistent") == 0

    def test_make_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            os.mkdir(src_dir)
            f1 = os.path.join(src_dir, "f1.txt")
            with open(f1, "w") as f: f.write("content")
            
            zip_path = os.path.join(tmpdir, "archive.zip")
            
            assert make_zip(src_dir, zip_path) is True
            assert os.path.exists(zip_path)
            
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as z:
                assert "f1.txt" in z.namelist()

    def test_sanitize_filename_for_upload(self):
        assert sanitize_filename_for_upload("0") == "0.renamed"
        assert sanitize_filename_for_upload("0.txt") == "0.txt"
        assert sanitize_filename_for_upload("normal_file.txt") == "normal_file.txt"
        assert sanitize_filename_for_upload("") == ""

    def test_restore_filename_from_download(self):
        assert restore_filename_from_download("0.renamed") == "0"
        assert restore_filename_from_download("0.renamed.txt") == "0.renamed.txt"
        assert restore_filename_from_download("normal_file.txt") == "normal_file.txt"
        assert restore_filename_from_download("0") == "0"