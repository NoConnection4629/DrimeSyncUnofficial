import toga
import pytest
def test_toga_switch_exists():
    assert hasattr(toga, 'Switch'), "toga.Switch does not exist"