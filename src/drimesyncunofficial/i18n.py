import json
import locale
import sys
import os

class I18n:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18n, cls).__new__(cls)
            cls._instance.translations = {}
            cls._instance.current_lang = "fr"   
            cls._instance.base_dir = os.path.dirname(os.path.abspath(__file__))
            cls._instance.load_language("fr")
            cls._instance.detect_language()
        return cls._instance

    def load_language(self, lang_code):
        """Loads a specific language file into memory if exists."""
        if lang_code in self.translations:
            return True

        try:
            json_path = os.path.join(self.base_dir, "locales", f"{lang_code}.json")
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                return True
            else:
                return False
        except Exception as e:
            print(f"[I18N] Error loading {lang_code}: {e}")
            return False

    def detect_language(self, forced_lang=None):
        try:
            lang_code = forced_lang
            if not lang_code: 
                if hasattr(sys, "getandroidapilevel"):
                    try:
                        from java.util import Locale
                        lang_code = Locale.getDefault().getLanguage()
                    except: pass
                
                if not lang_code:
                    try:
                        sys_loc = locale.getlocale()
                        if sys_loc and sys_loc[0]:
                            lang_code = sys_loc[0].split('_')[0]
                        else:
                            sys_loc_def = locale.getdefaultlocale()
                            if sys_loc_def and sys_loc_def[0]:
                                lang_code = sys_loc_def[0].split('_')[0]
                    except: pass
            
            if lang_code:
                lang_code = lang_code.lower()
                if self.load_language(lang_code):
                    self.current_lang = lang_code
                    print(f"[I18N] Language detected and loaded: {self.current_lang}")
                else:
                    print(f"[I18N] Language {lang_code} not supported, falling back to 'fr'")
            
        except Exception as e:
            print(f"[I18N] Detection error: {e}")

    def tr(self, key, default=None):
        """
        Main translation function.
        Usage: i18n.tr("menu_quit", "Quitter")
        """
        if self.current_lang in self.translations:
            if key in self.translations[self.current_lang]:
                return self.translations[self.current_lang][key]
        
        if "fr" in self.translations:
             if key in self.translations["fr"]:
                return self.translations["fr"][key]

        return default if default else key

_i18n_instance = I18n()

def tr(key, default=None):
    return _i18n_instance.tr(key, default)
