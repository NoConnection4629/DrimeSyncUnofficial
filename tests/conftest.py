import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from unittest.mock import MagicMock
mock_toga = MagicMock()
mock_toga.App = MagicMock 
sys.modules['toga'] = mock_toga
sys.modules['toga.style'] = MagicMock()
sys.modules['toga.style.pack'] = MagicMock()
@pytest.fixture
def mock_app_paths():
    paths = MagicMock()
    paths.data = MagicMock()
    paths.data.__truediv__.return_value = MagicMock()
    return paths
@pytest.fixture
def mock_windows_platform(monkeypatch):
    """Simulates running on Windows."""
    monkeypatch.setattr(sys, 'platform', 'win32')
    mock_toga = MagicMock()
    mock_toga.platform.current_platform = 'windows'
    monkeypatch.setitem(sys.modules, 'toga', mock_toga)
@pytest.fixture
def mock_linux_platform(monkeypatch):
    """Simulates running on Linux."""
    monkeypatch.setattr(sys, 'platform', 'linux')
    mock_toga = MagicMock()
    mock_toga.platform.current_platform = 'linux'
    monkeypatch.setitem(sys.modules, 'toga', mock_toga)

def pytest_addoption(parser):
    """Adds command line options for Real-World E2E testing."""
    parser.addoption(
        "--api-key", action="store", default=None, help="Drime API Token for Real-World E2E tests"
    )

@pytest.fixture(scope="session")
def api_key(request):
    return request.config.getoption("--api-key")