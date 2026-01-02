
import os
import hashlib
from PIL import Image
from drimesyncunofficial.filigranage_engine import OmegaEngine

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def test_randomness():
    print("Creating dummy image...")
    dummy = Image.new('RGB', (500, 500), color = 'white')
    dummy.save('test_src.jpg')

    engine = OmegaEngine()
    data = {
        "doc_hash": "1234567890",
        "uuid": "test-uuid",
        "to": "TEST USER",
        "ts": "2025-01-01",
        "author": "TEST"
    }
    options = {
        "microprint": True,
        "anti_copy": True,
        "mesh": True,
        "crypto_link": False, 
        "qr_triangulation": False
    }

    print("Generating Run 1...")
    engine.process_image('test_src.jpg', 'test_out_1.jpg', data, None, options)
    
    print("Generating Run 2...")
    engine.process_image('test_src.jpg', 'test_out_2.jpg', data, None, options)

    hash1 = md5('test_out_1.jpg')
    hash2 = md5('test_out_2.jpg')

    print(f"Hash 1: {hash1}")
    print(f"Hash 2: {hash2}")

    if hash1 == hash2:
        print("FAIL: Files are IDENTICAL. Randomness is NOT working.")
    else:
        print("SUCCESS: Files are DIFFERENT. Randomness is working.")

if __name__ == "__main__":
    test_randomness()
