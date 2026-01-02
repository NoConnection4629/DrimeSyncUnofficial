
from hypothesis import given, strategies as st
from drimesyncunofficial.format_utils import truncate_path_smart, format_size

# --- Utils Tests ---

@given(st.text())
def test_prop_truncate_path_smart_integrity(text):
    """
    PROPERTY: truncate_path_smart must NEVER crash.
    """
    try:
        res = truncate_path_smart(text, 20)
        assert isinstance(res, str)
        # Length check is tricky because logic is (part + ... + part)
        # 20 - 3 // 2 = 8.  8 + 3 + 8 = 19.
        # So len should be approx max_length.
    except Exception as e:
        import pytest
        pytest.fail(f"truncate_path_smart crashed on input {text!r}: {e}")

@given(st.text(), st.integers(min_value=5, max_value=100))
def test_prop_truncate_path_smart_length_check(text, limit):
    """
    PROPERTY: Output length should respect limit (approx).
    """
    res = truncate_path_smart(text, limit)
    
    if len(text) <= limit:
        assert res == text
    else:
        # Implementation: (limit - 3) // 2 for each side.
        # len = 2 * ((limit-3)//2) + 3.
        # Example: limit=10. (7)//2 = 3. 3+3+3 = 9. <= 10.
        # Example: limit=11. (8)//2 = 4. 4+3+4 = 11. <= 11.
        assert len(res) <= limit

@given(st.integers())
def test_prop_format_size(size):
    """
    PROPERTY: format_size should never crash.
    """
    res = format_size(size)
    assert isinstance(res, str)
    assert any(unit in res for unit in ["o", "Ko", "Mo", "Go", "To"]) or "0 o" in res
