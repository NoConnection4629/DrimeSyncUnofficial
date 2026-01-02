import pytest
import sys
from unittest.mock import MagicMock, patch
from drimesyncunofficial.utils import prevent_windows_sleep, _force_windows_backend, get_secure_secret, set_secure_secret
class TestWindowsSpecifics:
    def test_prevent_windows_sleep_on_windows(self, mock_windows_platform):
        """Test that SetThreadExecutionState is called on Windows."""
        with patch('ctypes.windll.kernel32.SetThreadExecutionState') as mock_set_state:
            prevent_windows_sleep()
            mock_set_state.assert_called_once_with(0x80000003)
    def test_prevent_windows_sleep_on_linux(self, mock_linux_platform):
        """Test that SetThreadExecutionState is NOT called on Linux."""
        with patch('ctypes.windll.kernel32.SetThreadExecutionState') as mock_set_state:
            prevent_windows_sleep()
            mock_set_state.assert_not_called()
    def test_force_windows_backend_on_windows(self, mock_windows_platform):
        """Test that keyring backend is set to Windows on Windows."""
        with patch('keyring.set_keyring') as mock_set_keyring:
            _force_windows_backend()
            mock_set_keyring.assert_called_once()
    def test_force_windows_backend_on_linux(self, mock_linux_platform):
        """Test that keyring backend is NOT set on Linux."""
        with patch('keyring.set_keyring') as mock_set_keyring:
            _force_windows_backend()
            mock_set_keyring.assert_not_called()
    def test_get_secure_secret_windows(self, mock_windows_platform):
        """Test retrieving a secret on Windows."""
        with patch('keyring.get_password', return_value="secret_value") as mock_get_pass:
            val = get_secure_secret("my_key")
            assert val == "secret_value"
            mock_get_pass.assert_called_with("DrimeSyncUnofficial", "my_key")
    def test_set_secure_secret_windows(self, mock_windows_platform):
        """Test setting a secret on Windows."""
        with patch('keyring.set_password') as mock_set_pass:
            success = set_secure_secret("my_key", "new_value")
            assert success is True
            mock_set_pass.assert_called_with("DrimeSyncUnofficial", "my_key", "new_value")
    def test_set_secure_secret_delete_windows(self, mock_windows_platform):
        """Test deleting a secret on Windows (setting empty value)."""
        with patch('keyring.delete_password') as mock_del_pass:
            success = set_secure_secret("my_key", "")
            assert success is True
            mock_del_pass.assert_called_with("DrimeSyncUnofficial", "my_key")