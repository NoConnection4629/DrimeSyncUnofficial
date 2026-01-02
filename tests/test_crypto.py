import os
import pytest
from drimesyncunofficial.utils import derive_key, E2EE_encrypt_file, E2EE_decrypt_file, E2EE_encrypt_name, E2EE_decrypt_name, E2EE_CRYPTO_ALGO
def test_crypto_algo_name():
    assert E2EE_CRYPTO_ALGO == "Argon2id + XChaCha20Poly1305 (IETF)"

def test_key_derivation():
    password = "test_password"
    salt = os.urandom(16)
    key = derive_key(password, salt)
    assert len(key) == 32, "Key should be 32 bytes for XChaCha20"

def test_file_encryption_decryption(tmp_path):
    password = "test_password"
    salt = os.urandom(16)
    key = derive_key(password, salt)
    
    content = b"Hello World, this is a secret message!"
    test_file = tmp_path / "test_secret.txt"
    test_file.write_bytes(content)
    
    encrypted_data = E2EE_encrypt_file(str(test_file), key)
    assert encrypted_data != content
    # XChaCha20 expects 24 byte nonce
    assert len(encrypted_data) > 24 + len(content) 

    decrypted_data = E2EE_decrypt_file(encrypted_data, key)
    assert decrypted_data == content

def test_name_encryption_decryption():
    password = "test_password"
    salt = os.urandom(16)
    key = derive_key(password, salt)
    
    name = "My Secret Document.pdf"
    enc_name = E2EE_encrypt_name(name, key)
    assert enc_name != name
    
    # Deterministic check (SIV)
    enc_name_2 = E2EE_encrypt_name(name, key)
    assert enc_name == enc_name_2

    dec_name = E2EE_decrypt_name(enc_name, key)
    assert dec_name == name

def test_name_encryption_special_chars():
    password = "test_password"
    salt = os.urandom(16)
    key = derive_key(password, salt)
    
    name = "Dossier éàù.test"
    enc_name = E2EE_encrypt_name(name, key)
    dec_name = E2EE_decrypt_name(enc_name, key)
    assert dec_name == name