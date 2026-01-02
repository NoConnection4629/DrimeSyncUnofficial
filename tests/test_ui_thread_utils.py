"""
Tests complets pour ui_thread_utils.py
Couvre toutes les fonctions de mise à jour thread-safe de l'UI.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import threading


class TestUIThreadUtils:
    """Tests pour les utilitaires de thread UI."""
    
    def test_safe_update_label_no_label(self):
        """Test safe_update_label quand label est None."""
        from drimesyncunofficial.ui_thread_utils import safe_update_label
        
        mock_app = Mock()
        mock_app.loop = Mock()
        
        # Should not crash
        safe_update_label(mock_app, None, "test")
        
        # Callback should still be queued
        assert mock_app.loop.call_soon_threadsafe.called
    
    def test_safe_update_label_basic(self):
        """Test mise à jour basique d'un label."""
        from drimesyncunofficial.ui_thread_utils import safe_update_label
        
        mock_app = Mock()
        mock_label = Mock()
        mock_label.text = ""
        
        # Simuler l'exécution directe de call_soon_threadsafe
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_update_label(mock_app, mock_label, "New Text")
        
        assert mock_label.text == "New Text"
    
    def test_safe_update_label_with_style(self):
        """Test mise à jour avec attributs de style."""
        from drimesyncunofficial.ui_thread_utils import safe_update_label
        
        mock_app = Mock()
        mock_label = Mock()
        mock_label.text = ""
        mock_label.style = Mock()
        mock_label.style.color = "black"
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_update_label(mock_app, mock_label, "Test", {'color': 'red'})
        
        assert mock_label.text == "Test"
        assert mock_label.style.color == "red"
    
    def test_safe_update_label_runtime_error(self):
        """Test gestion RuntimeError (widget détruit)."""
        from drimesyncunofficial.ui_thread_utils import safe_update_label
        
        mock_app = Mock()
        mock_label = Mock()
        
        # Setter qui lève RuntimeError (widget détruit)
        type(mock_label).text = property(
            lambda self: "",
            lambda self, value: (_ for _ in ()).throw(RuntimeError("Widget destroyed"))
        )
        
        def execute_callback(callback):
            callback()  # Should not crash despite RuntimeError
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        # Should not crash
        safe_update_label(mock_app, mock_label, "test")
    
    def test_safe_update_label_no_app_loop(self):
        """Test quand app n'a pas de loop."""
        from drimesyncunofficial.ui_thread_utils import safe_update_label
        
        mock_app = Mock(spec=[])  # Pas de 'loop' attribute
        mock_label = Mock()
        
        # Should not crash even without loop
        safe_update_label(mock_app, mock_label, "test")
    
    def test_safe_update_selection_basic(self):
        """Test mise à jour d'une sélection."""
        from drimesyncunofficial.ui_thread_utils import safe_update_selection
        
        mock_app = Mock()
        mock_selection = Mock()
        mock_selection.value = "old"
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_update_selection(mock_app, mock_selection, "new")
        
        assert mock_selection.value == "new"
    
    def test_safe_update_selection_none_selection(self):
        """Test quand selection est None."""
        from drimesyncunofficial.ui_thread_utils import safe_update_selection
        
        mock_app = Mock()
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        # Should not crash
        safe_update_selection(mock_app, None, "test")
    
    def test_safe_update_selection_exception(self):
        """Test gestion d'exception lors de mise à jour."""
        from drimesyncunofficial.ui_thread_utils import safe_update_selection
        
        mock_app = Mock()
        mock_selection = Mock()
        
        # Setter qui lève exception
        type(mock_selection).value = property(
            lambda self: "",
            lambda self, val: (_ for _ in ()).throw(ValueError("Invalid value"))
        )
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        # Should not crash
        safe_update_selection(mock_app, mock_selection, "test")
    
    def test_safe_log_basic(self):
        """Test ajout de log basique."""
        from drimesyncunofficial.ui_thread_utils import safe_log
        
        mock_app = Mock()
        mock_log = Mock()
        mock_log.value = "Existing log\n"
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_log(mock_app, mock_log, "New message")
        
        assert "New message" in mock_log.value
        assert "Existing log" in mock_log.value
    
    def test_safe_log_empty_initial(self):
        """Test log quand value initiale est None."""
        from drimesyncunofficial.ui_thread_utils import safe_log
        
        mock_app = Mock()
        mock_log = Mock()
        mock_log.value = None
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_log(mock_app, mock_log, "First message")
        
        assert mock_log.value == "First message\n"
    
    def test_safe_log_with_color(self):
        """Test log avec couleur (paramètre ignoré actuellement)."""
        from drimesyncunofficial.ui_thread_utils import safe_log
        
        mock_app = Mock()
        mock_log = Mock()
        mock_log.value = ""
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        safe_log(mock_app, mock_log, "Colored message", "red")
        
        # Color parameter is currently ignored (pass in implementation)
        assert "Colored message" in mock_log.value
    
    def test_safe_log_none_widget(self):
        """Test log quand widget est None."""
        from drimesyncunofficial.ui_thread_utils import safe_log
        
        mock_app = Mock()
        
        def execute_callback(callback):
            callback()
        
        mock_app.loop.call_soon_threadsafe = execute_callback
        
        # Should not crash
        safe_log(mock_app, None, "test")
    
    def test_run_in_background_basic(self):
        """Test lancement fonction en background."""
        from drimesyncunofficial.ui_thread_utils import run_in_background
        import time
        
        result = []
        
        def background_task(value):
            result.append(value)
        
        thread = run_in_background(background_task, "test_value")
        
        assert isinstance(thread, threading.Thread)
        assert thread.daemon is True
        
        # Wait for thread
        thread.join(timeout=1.0)
        assert result == ["test_value"]
    
    def test_run_in_background_with_kwargs(self):
        """Test background avec kwargs."""
        from drimesyncunofficial.ui_thread_utils import run_in_background
        
        result = {}
        
        def background_task(key=None, value=None):
            result[key] = value
        
        thread = run_in_background(background_task, key="test", value=123)
        thread.join(timeout=1.0)
        
        assert result == {"test": 123}
    
    def test_run_in_background_exception_handling(self):
        """Test que les exceptions dans le thread ne crashent pas l'app."""
        from drimesyncunofficial.ui_thread_utils import run_in_background
        
        def failing_task():
            raise ValueError("Test error")
        
        # Should not crash main thread
        thread = run_in_background(failing_task)
        thread.join(timeout=1.0)
        
        # Thread should complete despite exception
        assert not thread.is_alive()
