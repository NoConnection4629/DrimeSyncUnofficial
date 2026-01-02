import pytest
from unittest.mock import MagicMock, patch, ANY
import sys
if 'toga' not in sys.modules:
    sys.modules['toga'] = MagicMock()
import toga
from toga.style import Pack
from drimesyncunofficial.about import AboutManager

@pytest.fixture
def mock_app():
    return MagicMock()

def test_initialization(mock_app):
    manager = AboutManager(mock_app)
    assert manager.app == mock_app
    assert manager.window is None

def test_show(mock_app):
    manager = AboutManager(mock_app)
    with patch('toga.Window') as mock_window, \
         patch('toga.Box'), \
         patch('toga.Button'), \
         patch('toga.MultilineTextInput') as mock_text_input, \
         patch('drimesyncunofficial.about.tr') as mock_tr:
        
        mock_tr.return_value = "DRIMESYNC - TEST TEXT"
        
        manager.show()
        
        mock_app.changer_ecran.assert_called_once()
        mock_text_input.assert_called()
        mock_tr.assert_called_with("about_main_text", "About text")

def test_about_uses_translation():
    from drimesyncunofficial.about import AboutManager
    from drimesyncunofficial.i18n import tr
    
    about_text = tr("about_main_text", "fallback")
    assert len(about_text) > 100

if __name__ == "__main__":
    pytest.main([__file__])