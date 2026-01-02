
import pytest
import shutil
import tempfile
import functools
import json
import os
from unittest.mock import patch, MagicMock
from drimesyncunofficial.i18n import I18n

class TestLocalizationExtreme:

    @pytest.fixture
    def i18n_instance(self):
        """Fixture to provide a fresh I18n instance for each test, 
        isolating it from global state."""
        # Create a temporary directory for locales
        self.test_dir = tempfile.mkdtemp()
        self.locale_dir = os.path.join(self.test_dir, "locales")
        os.makedirs(self.locale_dir)
        
        # Initialize I18n with this path
        # We need to monkeypatch the base_dir because __new__ singleton logic 
        # makes it hard to re-init properly in some designs, but let's try to reset it.
        I18n._instance = None # Force reset singleton
        
        with patch("drimesyncunofficial.i18n.os.path.dirname") as mock_dirname:
            # Mock dirname to return our test_dir so it looks for 'locales' inside it
            # The code uses: base_dir = os.path.dirname(os.path.abspath(__file__))
            # We want base_dir to be self.test_dir
            # So dirname should return self.test_dir when called with abspath result
            
            # Actually easier: just manually set base_dir after init if possible,
            # or better, sub-class or mock.
            # Let's use a patch on the class usage in the test.
            pass

        i18n = I18n()
        # Forcing the base_dir to our temp dir for testing
        i18n.base_dir = self.test_dir
        i18n.translations = {} # Reset translations
        
        yield i18n
        
        # Teardown
        shutil.rmtree(self.test_dir)
        I18n._instance = None # Reset singleton

    def create_locale_file(self, i18n, lang_code, content):
        path = os.path.join(i18n.base_dir, "locales", f"{lang_code}.json")
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(content, str): # Raw string content (for malformed tests)
                f.write(content)
            else:
                json.dump(content, f)
        return path

    def test_language_switching(self, i18n_instance):
        """Verify dynamic language switching works."""
        self.create_locale_file(i18n_instance, "en", {"hello": "Hello"})
        self.create_locale_file(i18n_instance, "es", {"hello": "Hola"})
        
        # Load English
        i18n_instance.load_language("en")
        i18n_instance.current_lang = "en"
        assert i18n_instance.tr("hello") == "Hello"
        
        # Switch to Spanish
        i18n_instance.load_language("es")
        i18n_instance.current_lang = "es"
        assert i18n_instance.tr("hello") == "Hola"

    def test_fallback_mechanism(self, i18n_instance):
        """Verify fallback to 'fr' (default) when key is missing in current lang."""
        # Create 'fr' as base/fallback
        self.create_locale_file(i18n_instance, "fr", {"only_in_fr": "Bonjour", "common": "Salut"})
        # Create 'en' with missing key
        self.create_locale_file(i18n_instance, "en", {"common": "Hi"})
        
        i18n_instance.load_language("fr")
        i18n_instance.load_language("en")
        i18n_instance.current_lang = "en"
        
        # Key exists in EN
        assert i18n_instance.tr("common") == "Hi"
        # Key missing in EN -> Fallback to FR
        assert i18n_instance.tr("only_in_fr") == "Bonjour"
        
    def test_fallback_to_default_arg(self, i18n_instance):
        """Verify fallback to default argument when key missing everywhere."""
        i18n_instance.translations = {}
        assert i18n_instance.tr("missing_key", "Default Value") == "Default Value"

    def test_special_characters_cjk(self, i18n_instance):
        """Verify correct handling of CJK characters."""
        content = {
            "msg_zh": "你好", # Chinese
            "msg_ja": "こんにちは" # Japanese
        }
        self.create_locale_file(i18n_instance, "asia", content)
        i18n_instance.load_language("asia")
        i18n_instance.current_lang = "asia"
        
        assert i18n_instance.tr("msg_zh") == "你好"
        assert i18n_instance.tr("msg_ja") == "こんにちは"

    def test_special_characters_latin(self, i18n_instance):
        """Verify correct handling of accented Latin characters."""
        content = {
            "msg_pl": "Zażółć gęślą jaźń", 
            "msg_sv": "Sju sjösjuka sjömän",
            "msg_fr": "Élève à l'école"
        }
        self.create_locale_file(i18n_instance, "eur", content)
        i18n_instance.load_language("eur")
        i18n_instance.current_lang = "eur"
        
        assert i18n_instance.tr("msg_pl") == "Zażółć gęślą jaźń"
        assert i18n_instance.tr("msg_sv") == "Sju sjösjuka sjömän"
        assert i18n_instance.tr("msg_fr") == "Élève à l'école"

    def test_malformed_json_handling(self, i18n_instance, capsys):
        """Verify app does not crash on malformed JSON."""
        # Create a file with broken JSON syntax
        self.create_locale_file(i18n_instance, "bad", "{ broken_json: true ") 
        
        # Attempt to load - should return False and print error (not raise)
        result = i18n_instance.load_language("bad")
        assert result is False
        
        # Verify specific error logging if possible, but mainly ensure no crash
        captured = capsys.readouterr()
        assert "Error loading bad" in captured.out or "Error loading bad" in captured.err

    def test_missing_file_handling(self, i18n_instance):
        """Verify loading non-existent file returns False safely."""
        result = i18n_instance.load_language("non_existent_lang")
        assert result is False
