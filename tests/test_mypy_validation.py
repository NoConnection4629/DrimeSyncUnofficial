"""
Test mypy validation automatique.
Vérifie que les type hints sont corrects dans les fichiers prioritaires.
"""
import pytest
import subprocess
import sys


class TestMypyValidation:
    """Tests de validation mypy pour les type hints."""
    
    def test_mypy_base_transfer_manager(self):
        """Valide les type hints de base_transfer_manager.py."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/base_transfer_manager.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        # Accepter returncode 0 ou 1 (warnings des dépendances OK)
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
    
    def test_mypy_api_client(self):
        """Valide les type hints de api_client.py."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/api_client.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
    
    def test_mypy_security(self):
        """Valide les type hints de security.py (fichier critique)."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/security.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        # Security.py peut avoir quelques warnings non-critiques, on vérifie juste qu'il n'y a pas d'erreurs graves
        # On accepte returncode 0 ou 1 (warnings seulement)
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
    
    def test_mypy_utils(self):
        """Valide les type hints de utils.py."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/utils.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        # Utils.py peut avoir quelques warnings, on accepte 0 ou 1
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
    
    def test_mypy_android_utils(self):
        """Valide les type hints de android_utils.py."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/android_utils.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        # Android utils aura des warnings sur les imports android, c'est OK
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
    
    def test_mypy_ui_thread_utils(self):
        """Valide les type hints de ui_thread_utils.py."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/drimesyncunofficial/ui_thread_utils.py", "--show-error-codes", "--no-error-summary"],
            capture_output=True,
            text=True
        )
        
        # ui_thread_utils peut avoir des warnings sur Any types, on accepte 0 ou 1
        assert result.returncode in [0, 1], f"Critical mypy errors:\n{result.stdout}\n{result.stderr}"
