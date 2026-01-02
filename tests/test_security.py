import pytest
from drimesyncunofficial.utils import (
    derive_key, 
    E2EE_encrypt_name, 
    E2EE_decrypt_name, 
    E2EE_encrypt_file, 
    E2EE_decrypt_file
)
import os
import tempfile
class TestSecurity:
    @pytest.fixture
    def secret_key(self):
        return os.urandom(32)
    def test_derive_key(self):
        password = "my_secure_password"
        salt = os.urandom(16)
        key1 = derive_key(password, salt)
        key2 = derive_key(password, salt)
        assert key1 == key2
        assert len(key1) > 0
        
        salt2 = os.urandom(16)
        key3 = derive_key(password, salt2)
        assert key1 != key3
    def test_encrypt_decrypt_name(self, secret_key):
        original_name = "My Secret File.txt"
        encrypted = E2EE_encrypt_name(original_name, secret_key)
        assert encrypted != original_name
        assert encrypted is not None
        decrypted = E2EE_decrypt_name(encrypted, secret_key)
        assert decrypted == original_name
    def test_encrypt_decrypt_name_special_chars(self, secret_key):
        original_name = "Dossier ébène & @ #.tmp"
        encrypted = E2EE_encrypt_name(original_name, secret_key)
        decrypted = E2EE_decrypt_name(encrypted, secret_key)
        assert decrypted == original_name
    def test_encrypt_decrypt_file(self, secret_key):
        content = b"This is a secret message."
        with tempfile.NamedTemporaryFile(delete=False) as tmp_in:
            tmp_in.write(content)
            tmp_in_path = tmp_in.name
        try:
            encrypted_data = E2EE_encrypt_file(tmp_in_path, secret_key)
            assert encrypted_data != content
            assert len(encrypted_data) > 0
            decrypted_data = E2EE_decrypt_file(encrypted_data, secret_key)
            assert decrypted_data == content
        finally:
            if os.path.exists(tmp_in_path):
                os.remove(tmp_in_path)
    def test_decrypt_invalid_token(self, secret_key):
        invalid_data = b"invalid_encrypted_data"
        result = E2EE_decrypt_file(invalid_data, secret_key)
        assert result is None