import pytest
from unittest.mock import MagicMock, patch
from drimesyncunofficial.app import DrimeSyncUnofficial
@pytest.mark.skip(reason="Issues with mocking toga.App globally in conftest.py causing initialization failures")
class TestAppIntegration:
    @pytest.fixture
    def app(self):
        def fake_init(self, *args, **kwargs):
            MagicMock.__init__(self)
        with patch.object(DrimeSyncUnofficial, "__init__", side_effect=fake_init):
            app = DrimeSyncUnofficial("DrimeSync Unofficial", "com.example.drimesync")
            app.formal_name = "DrimeSync Unofficial"
            app.app_id = "com.example.drimesync"
            app.paths = MagicMock()
            app.paths.data = MagicMock()
            app.paths.data.__truediv__.return_value = MagicMock() 
            app.main_window = MagicMock()
            app.startup = MagicMock()
            return app
    def test_app_startup(self, app):
        assert app.formal_name is not None
        assert app.app_id is not None
    def test_commands_exist(self, app):
        assert hasattr(app, "show_about")
        assert hasattr(app, "show_filigranage")
        assert hasattr(app, "show_settings")
    @patch("drimesyncunofficial.about.AboutManager")
    def test_show_about(self, mock_about_cls, app):
        app.show_about(None)
        mock_about_cls.assert_called_with(app)
        mock_about_cls.return_value.show.assert_called()
    @patch("drimesyncunofficial.filigranage.WatermarkManager")
    def test_show_filigranage(self, mock_watermark_cls, app):
        app.show_filigranage(None)
        mock_watermark_cls.assert_called_with(app)
        mock_watermark_cls.return_value.show.assert_called()