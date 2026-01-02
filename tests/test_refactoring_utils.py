
import pytest
import drimesyncunofficial.utils as utils
import drimesyncunofficial.crypto_utils as crypto_utils
import drimesyncunofficial.format_utils as format_utils

def test_crypto_utils_imports():
    """Verify that crypto functions are present in crypto_utils."""
    assert hasattr(crypto_utils, 'derive_key')
    assert hasattr(crypto_utils, 'E2EE_encrypt_file')
    assert hasattr(crypto_utils, 'get_salt_path')
    assert hasattr(crypto_utils, 'E2EE_encrypt_name')

def test_format_utils_imports():
    """Verify that format functions are present in format_utils."""
    assert hasattr(format_utils, 'truncate_path_smart')
    assert hasattr(format_utils, 'format_size')
    assert hasattr(format_utils, 'format_display_date')

def test_utils_facade():
    """Verify that utils still exports the functions (Facade pattern)."""
    assert hasattr(utils, 'derive_key')
    assert hasattr(utils, 'truncate_path_smart')
    assert hasattr(utils, 'load_exclusion_patterns') # Original, not moved
    
def test_functionality_parity():
    """Check that a function works the same way from both locations."""
    name = "very_long_file_name_that_should_be_truncated.txt"
    res1 = utils.truncate_path_smart(name, 20)
    res2 = format_utils.truncate_path_smart(name, 20)
    assert res1 == res2
    assert "..." in res1
