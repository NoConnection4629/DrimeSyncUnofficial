
import pytest
from unittest.mock import MagicMock, patch
from drimesyncunofficial.mixins import LoggerMixin

class MixedParams(LoggerMixin):
    """Classe fictive pour tester le mixin"""
    def __init__(self):
        # On ne définit pas self.app initialement pour tester la résilience
        pass

@pytest.fixture
def logger_mixin():
    return MixedParams()

@patch('drimesyncunofficial.mixins.update_logs_threadsafe')
def test_log_ui_truncation_extreme(mock_update, logger_mixin):
    """
    EXTREME: Teste la troncature avec un message massivement long (10k chars).
    Doit tronquer à 500 chars + suffixe.
    """
    long_message = "A" * 10000
    expected_msg = "A" * 500 + "... [TRUNCATED]"
    
    logger_mixin.log_ui(long_message)
    
    mock_update.assert_called_once()
    args, _ = mock_update.call_args
    assert args[1] == expected_msg
    assert len(args[1]) == 515 # 500 + 15 chars de suffixe

@patch('drimesyncunofficial.mixins.update_logs_threadsafe')
def test_log_ui_resilience_types(mock_update, logger_mixin):
    """
    EXTREME: Envoie des types non-string (None, int, dict, Exception).
    Ne doit PAS crasher et doit convertir en string.
    """
    # Test None
    logger_mixin.log_ui(None)
    mock_update.assert_called_with(logger_mixin, "None", None)
    
    # Test Int
    logger_mixin.log_ui(12345)
    mock_update.assert_called_with(logger_mixin, "12345", None)
    
    # Test Dict
    logger_mixin.log_ui({"key": "val"})
    mock_update.assert_called_with(logger_mixin, "{'key': 'val'}", None)
    
    # Test Exception
    logger_mixin.log_ui(ValueError("Oups"))
    mock_update.assert_called_with(logger_mixin, "Oups", None)

@patch('drimesyncunofficial.mixins.update_logs_threadsafe')
def test_log_ui_debug_filtering(mock_update, logger_mixin):
    """
    EXTREME: Teste la logique de filtrage debug.
    """
    # Cas 1: Pas d'app -> Doit ignorer le log debug (sécurité)
    logger_mixin.log_ui("Debug Msg", debug=True)
    mock_update.assert_not_called()
    
    # Setup App Mock
    logger_mixin.app = MagicMock()
    logger_mixin.app.config_data = {}

    # Cas 2: App présente mais debug_mode=False (défaut) -> Doit ignorer
    logger_mixin.log_ui("Debug Msg 2", debug=True)
    mock_update.assert_not_called()

    # Cas 3: App présente et debug_mode=True -> Doit logger
    logger_mixin.app.config_data = {'debug_mode': True}
    logger_mixin.log_ui("Debug Msg 3", debug=True)
    mock_update.assert_called_once_with(logger_mixin, "Debug Msg 3", None)

@patch('drimesyncunofficial.mixins.update_logs_threadsafe')
def test_log_ui_boundary_exact(mock_update, logger_mixin):
    """
    EXTREME: Teste les limites exactes (499, 500, 501 chars).
    """
    # 499 chars
    msg_499 = "B" * 499
    logger_mixin.log_ui(msg_499)
    mock_update.assert_called_with(logger_mixin, msg_499, None)
    
    # 500 chars (Limite exacte)
    msg_500 = "C" * 500
    logger_mixin.log_ui(msg_500)
    mock_update.assert_called_with(logger_mixin, msg_500, None)
    
    # 501 chars (Dépassement de 1)
    msg_501 = "D" * 501
    expected_501 = "D" * 500 + "... [TRUNCATED]"
    logger_mixin.log_ui(msg_501)
    mock_update.assert_called_with(logger_mixin, expected_501, None)
