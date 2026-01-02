
import pytest
from drimesyncunofficial.utils import truncate_path_smart

def test_truncate_path_smart_short():
    assert truncate_path_smart("short.pdf") == "short.pdf"

def test_truncate_path_smart_exact():
    name = "a" * 35
    assert truncate_path_smart(name, 35) == name

def test_truncate_path_smart_long():
    name = "a" * 40
    truncated = truncate_path_smart(name, 35)
    assert len(truncated) <= 35 + 3 # It might be slightly longer due to ... logic but usually fits target visual width
    assert "..." in truncated
    assert truncated.startswith("aaaaaaaaaaaaaaa")
    assert truncated.endswith("aaaaaaaaaaaaaaaa") # 35-3 // 2 = 16

def test_truncate_path_smart_filename():
    name = "mon_fichier_de_vacances_tres_long_2025.pdf"
    # Length is 42
    # Target 35
    # (35-3)//2 = 16
    expected = "mon_fichier_de_v...g_2025.pdf" 
    # mon_fichier_de_v (16)
    # ... (3)
    # _long_2025.pdf (14)? No logic is name[-16:] => "ong_2025.pdf" (12 chars? wait)
    # name len 42. name[-16:] is last 16 chars.
    # "ong_2025.pdf" is 12 chars.
    # "tres_long_2025.pdf" is 18 chars.
    # Last 16: "es_long_2025.pdf"
    
    truncated = truncate_path_smart(name, 35)
    assert truncated == "mon_fichier_de_v...es_long_2025.pdf"

if __name__ == "__main__":
    pytest.main([__file__])
