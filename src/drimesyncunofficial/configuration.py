import toga
import asyncio
import json
import os
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import (
    COL_VERT, COL_GRIS, COL_TEXT_GRIS, COL_JAUNE, COL_ROUGE, COL_VIOLET, COL_BLEU, COL_BLEU2,
    CONF_KEY_API_KEY, CONF_KEY_WORKERS, CONF_KEY_SEMAPHORES, CONF_KEY_DEBUG_MODE,
    CONF_KEY_USE_EXCLUSIONS, CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD,
    CONF_KEY_2FA_SECRET, CONF_KEY_LANGUAGE
)
from drimesyncunofficial.i18n import tr
from drimesyncunofficial.utils import get_global_exclusion_path, set_secure_secret
from drimesyncunofficial.android_utils import request_ignore_battery_optimizations_intent, is_ignoring_battery_optimizations
from drimesyncunofficial.security import SecurityManager
from drimesyncunofficial.about import AboutManager
from drimesyncunofficial.ui_utils import create_back_button

class LanguageSelector:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.selection_input = None

    def show(self):
        box = toga.Box(style=Pack(direction=COLUMN, margin=10))
        box.add(toga.Label("Sélectionnez la langue de l'interface :", style=Pack(margin_bottom=5, font_weight=BOLD)))
        
        lang_map = {
            "fr": "Français", "en": "English", "de": "Deutsch", "es": "Español",
            "pt": "Português", "it": "Italiano", "nl": "Nederlands", "pl": "Polski",
            "sv": "Svenska", "zh": "中文 (Chinese)", "ja": "日本語 (Japanese)"
        }
        
        locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        available_codes = []
        if os.path.exists(locales_dir):
            for f in os.listdir(locales_dir):
                if f.endswith(".json"):
                    code = f.replace(".json", "")
                    available_codes.append(code)
        
        available_codes.sort()
        
        items = []
        current_selection = None
        current_lang_code = self.app.config_data.get(CONF_KEY_LANGUAGE, "fr")
        
        self.code_map = {} 
        
        for code in available_codes:
            name = lang_map.get(code, code.upper())
            label = f"{name} [{code}]"
            items.append(label)
            self.code_map[label] = code
            if code == current_lang_code:
                current_selection = label

        if not current_selection and items:
             current_selection = items[0]

        self.selection_input = toga.Selection(items=items, style=Pack(margin_bottom=20))
        if current_selection:
            self.selection_input.value = current_selection

        box.add(self.selection_input)

        btn_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        btn_box.add(toga.Button("Annuler", on_press=self.app.retour_arriere, style=Pack(flex=1, margin_right=5)))
        btn_box.add(toga.Button("Sauvegarder", on_press=self.save, style=Pack(flex=1, margin_left=5, background_color=COL_VERT, color='white', font_weight=BOLD)))
        box.add(btn_box)
        
        self.app.changer_ecran(box)

    def save(self, widget):
        label = self.selection_input.value
        code = self.code_map.get(label)
        
        if code:
            self.app.config_data[CONF_KEY_LANGUAGE] = code
            self.app.config_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                try:
                    with open(self.app.config_path, 'r', encoding='utf-8') as f:
                         data = json.load(f)
                except FileNotFoundError:
                    data = {}
                data[CONF_KEY_LANGUAGE] = code
                with open(self.app.config_path, 'w', encoding='utf-8') as f:
                     json.dump(data, f, indent=4)
                
                self.app.main_window.info_dialog("Langue Changée / Language Changed", "Veuillez redémarrer l'application pour appliquer le changement.\nPlease restart the app.")
            except Exception as e:
                self.app.main_window.error_dialog("Erreur", f"Impossible de sauvegarder : {e}")

        self.app.retour_arriere(widget)

class ExclusionEditor:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.txt_content = None
    def show(self):
        box = toga.Box(style=Pack(direction=COLUMN, margin=10))
        box.add(toga.Label("Entrez un motif par ligne (*.tmp, dossier/, etc.) :", style=Pack(margin_bottom=5)))
        path = get_global_exclusion_path(self.app.paths)
        if not path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                default_content = [
                    "# Liste des fichiers/dossiers à ignorer (format glob)",
                    "*.tmp", "*.bak", "*.swp", "*.old", "*.trashed*", "*.thumbnail*", "*.thumbnails*",
                    "Thumbs.db", ".DS_Store", "._*",
                    "__pycache__/", ".git/", ".idea/", ".vscode/",
                    "node_modules/", "venv/", ".env",
                    "~$*" 
                ]
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(default_content))
            except: pass
        initial_content = ""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f: initial_content = f.read()
            except: pass
        self.txt_content = toga.MultilineTextInput(value=initial_content, style=Pack(flex=1, font_family='monospace', margin_bottom=10))
        box.add(self.txt_content)
        btn_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        btn_box.add(toga.Button(tr("btn_cancel", "Annuler"), on_press=self.app.retour_arriere, style=Pack(flex=1, margin_right=5)))
        btn_box.add(toga.Button(tr("btn_save", "Sauvegarder"), on_press=self.save, style=Pack(flex=1, margin_left=5, background_color=COL_VERT, color='white', font_weight=BOLD)))
        box.add(btn_box)
        self.app.changer_ecran(box)
    def save(self, widget):
        path = get_global_exclusion_path(self.app.paths)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.txt_content.value)
            self.app.retour_arriere(widget)
        except Exception as e:
            self.app.main_window.error_dialog("Erreur", f"Impossible d'écrire le fichier : {e}")
class ConfigManager:
    def __init__(self, app): 
        self.app = app
        self.window = None
        self.input_api = None
        self.chk_debug = None
        self.chk_exclusions = None 
        self.input_workers = None
        self.input_semaphores = None
    def show(self):
        main_container = toga.ScrollContainer()
        box = toga.Box(style=Pack(direction=COLUMN, margin=20, flex=1))
        
        box.add(toga.Label(tr("cfg_lbl_lang", "Langue / Language :"), style=Pack(margin_bottom=5, font_weight=BOLD)))
        cur_lang = self.app.config_data.get(CONF_KEY_LANGUAGE, 'auto')
        btn_lang = toga.Button(f"🌐 {tr('cfg_btn_change_lang', 'Changer de langue')} ({cur_lang})", on_press=self.open_language_selector, style=Pack(margin_bottom=10))
        box.add(btn_lang)
        box.add(toga.Divider(style=Pack(margin_top=5, margin_bottom=10)))

        current_key = self.app.config_data.get(CONF_KEY_API_KEY, '')
        api_key_configured = bool(current_key)
        box.add(toga.Label(tr("cfg_api_title", "Gestion API :"), style=Pack(margin_bottom=5, font_weight=BOLD)))
        if api_key_configured:
            box.add(toga.Label(tr("cfg_api_configured", "🔐 Clé API configurée"), style=Pack(margin_bottom=10, color='green')))
            box.add(toga.Button(tr("cfg_btn_reset_key", "Réinitialiser la Clé"), on_press=self.action_reset_key_ui, style=Pack(width=200, background_color=COL_JAUNE, color='white', margin_bottom=15)))
            self.input_api = None 
        else:
            self.input_api = toga.TextInput(value=current_key, placeholder='sk-...', style=Pack(margin_bottom=15))
            box.add(self.input_api)
        box.add(toga.Divider(style=Pack(margin_top=10, margin_bottom=10)))
        box.add(toga.Label('Sécurité & Chiffrement :', style=Pack(margin_bottom=10, font_weight=BOLD)))
        btn_security = toga.Button(tr("cfg_btn_security", "🛡️ Configurer le Chiffrement"), on_press=self.open_security, style=Pack(width=300, height=40, background_color=COL_VIOLET, color='white', margin_bottom=10))
        box.add(btn_security)

        if toga.platform.current_platform == 'android':
            perm_status = "❌"
            try:
                from android.os import Environment, Build
                if Build.VERSION.SDK_INT >= 30:
                    if Environment.isExternalStorageManager():
                        perm_status = "✅"
            except:
                pass
            
            
            btn_android_perm = toga.Button(
                f'{perm_status} Activer les permissions de stockage',
                on_press=self.action_demander_permissions,
                style=Pack(width=300, height=40, background_color=COL_BLEU2, color='white', margin_bottom=10)
            )
            box.add(btn_android_perm)

            batt_status = "❌"
            if is_ignoring_battery_optimizations():
                batt_status = "✅"
            
            btn_batt = toga.Button(
                f'{batt_status} Background (Expérimental)',
                on_press=self.action_ignore_battery,
                style=Pack(width=300, height=40, background_color=COL_BLEU2, color='white', margin_bottom=10)
            )
            box.add(btn_batt)
        box.add(toga.Divider(style=Pack(margin_top=10, margin_bottom=10)))
        box.add(toga.Label(tr("cfg_title_perf", "Performance :"), style=Pack(margin_bottom=10, font_weight=BOLD)))
        row_w = toga.Box(style=Pack(direction=ROW, align_items=CENTER, margin_bottom=5))
        row_w.add(toga.Label(tr("cfg_lbl_workers", "Workers (1-30) :"), style=Pack(width=150)))
        self.input_workers = toga.NumberInput(min=1, max=30, step=1, value=self.app.config_data.get(CONF_KEY_WORKERS, 5), style=Pack(flex=1))
        row_w.add(self.input_workers)
        box.add(row_w)
        row_s = toga.Box(style=Pack(direction=ROW, align_items=CENTER, margin_bottom=5))
        row_s.add(toga.Label(tr("cfg_lbl_semaphores", "Sémaphores (0-30) :"), style=Pack(width=150)))
        self.input_semaphores = toga.NumberInput(min=0, max=30, step=1, value=self.app.config_data.get(CONF_KEY_SEMAPHORES, 0), style=Pack(flex=1))
        row_s.add(self.input_semaphores)
        box.add(row_s)
        box.add(toga.Label(tr("cfg_lbl_perf_rec", "Recommandé : Workers=5, Sémaphores=0 (Auto)"), style=Pack(font_size=8, color='gray', margin_bottom=15)))
        box.add(toga.Divider(style=Pack(margin_top=10, margin_bottom=10)))
        box.add(toga.Label(tr("cfg_title_adv", "Options Avancées :"), style=Pack(margin_bottom=10, font_weight=BOLD)))
        use_exc = self.app.config_data.get(CONF_KEY_USE_EXCLUSIONS, True)
        row_exc = toga.Box(style=Pack(direction=ROW, align_items=CENTER, margin_bottom=10))
        self.chk_exclusions = toga.Switch(tr("cfg_chk_exclusions", "Utiliser les exclusions"), value=use_exc)
        btn_edit_exc = toga.Button(tr("cfg_btn_manage_exc", "Gérer la liste..."), on_press=self.open_exclusion_editor, style=Pack(width=120, margin_left=10))
        row_exc.add(self.chk_exclusions)
        row_exc.add(btn_edit_exc)
        row_exc.add(toga.Box(style=Pack(flex=1)))
        box.add(row_exc)
        is_debug = self.app.config_data.get(CONF_KEY_DEBUG_MODE, False)
        self.chk_debug = toga.Switch(tr("cfg_chk_debug", "🐛 Mode Debug (Logs détaillés)"), value=is_debug, style=Pack(margin_bottom=15))
        box.add(self.chk_debug)
        box.add(toga.Divider(style=Pack(margin_top=10, margin_bottom=10)))
        box.add(toga.Label(tr("cfg_title_info", "Informations :"), style=Pack(margin_bottom=10, font_weight=BOLD)))
        box_about = toga.Box(style=Pack(direction=ROW, margin_bottom=15))
        btn_about = toga.Button(tr("cfg_btn_about", "❓ À propos / Aide"), on_press=self.open_about, style=Pack(flex=1))
        box_about.add(btn_about)
        box.add(box_about)
        row_f = toga.Box(style=Pack(direction=ROW, margin_top=20))
        row_f.add(create_back_button(self.app.retour_arriere, width=100, margin_bottom=0, margin_right=5))
        btn_save = toga.Button(tr("cfg_btn_save", "Enregistrer"), on_press=self.save_config_action, style=Pack(flex=1, margin_left=5, background_color=COL_VERT, color='white', font_weight=BOLD))
        row_f.add(btn_save)
        box.add(row_f)
        main_container.content = box
        self.app.changer_ecran(main_container)
    def open_security(self, widget):
        SecurityManager(self.app).show()
    def open_language_selector(self, widget):
        LanguageSelector(self.app).show()
    def open_exclusion_editor(self, widget):
        ExclusionEditor(self.app).show()
    def open_about(self, widget):
        """Affiche la fenêtre d'aide et de disclaimer."""
        AboutManager(self.app).show()
    def action_reset_key_ui(self, widget):
        self.app.config_data[CONF_KEY_API_KEY] = ""
        set_secure_secret(CONF_KEY_API_KEY, "")
        if hasattr(self.app, 'api_client'):
            self.app.api_client.set_api_key("")
        self.app.retour_arriere(widget)
        self.show()
    async def save_config_action(self, widget):
        new_config = self.app.config_data.copy()
        api_val = ""
        if self.input_api: 
            api_val = self.input_api.value.strip()
            new_config[CONF_KEY_API_KEY] = api_val
            if hasattr(self.app, 'api_client'):
                self.app.api_client.set_api_key(api_val)
        try:
            new_config[CONF_KEY_WORKERS] = int(self.input_workers.value) if self.input_workers.value else 5
        except: new_config[CONF_KEY_WORKERS] = 5
        try:
            new_config[CONF_KEY_SEMAPHORES] = int(self.input_semaphores.value) if self.input_semaphores.value else 0
        except: new_config[CONF_KEY_SEMAPHORES] = 0
        if self.chk_debug: new_config[CONF_KEY_DEBUG_MODE] = self.chk_debug.value
        if self.chk_exclusions: new_config[CONF_KEY_USE_EXCLUSIONS] = self.chk_exclusions.value
        is_desktop = toga.platform.current_platform not in {'android', 'iOS', 'web'}
        secure_save_success = False
        if is_desktop:
            key_to_save = new_config.get(CONF_KEY_API_KEY, '')
            if key_to_save:
                secure_save_success = set_secure_secret(CONF_KEY_API_KEY, key_to_save)
            pass_to_save = new_config.get(CONF_KEY_E2EE_PASSWORD, '')
            if pass_to_save: set_secure_secret(CONF_KEY_E2EE_PASSWORD, pass_to_save)
            sec_2fa_to_save = new_config.get(CONF_KEY_2FA_SECRET, '')
            if sec_2fa_to_save: set_secure_secret(CONF_KEY_2FA_SECRET, sec_2fa_to_save)
        json_config = new_config.copy()
        if is_desktop and secure_save_success:
            json_config[CONF_KEY_API_KEY] = "" 
            json_config[CONF_KEY_E2EE_PASSWORD] = ""
            json_config[CONF_KEY_2FA_SECRET] = ""
        else:
            pass
        try:
            self.app.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.app.config_path, 'w', encoding='utf-8') as f: 
                json.dump(json_config, f, indent=4)
            self.app.config_data = new_config 
            self.app.retour_arriere(widget)
            asyncio.create_task(self.app.verify_api_startup())
        except Exception as e: 
            await self.app.main_window.error_dialog("Erreur", f"{e}")

    def action_demander_permissions(self, widget):
        """
        Ouvre les paramètres Android 'Accès à tous les fichiers' spécifiquement pour cette app.
        """
        if toga.platform.current_platform != 'android':
            return

        try:
            from android.content import Intent
            from android.net import Uri
            from android.provider import Settings
            from android.os import Build, Environment
            
            if Build.VERSION.SDK_INT >= 30:
                if Environment.isExternalStorageManager():
                     self.app.main_window.info_dialog("C'est tout bon !", "L'accès à tous les fichiers est déjà activé. ✅")
                else:
                    try:
                        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                        uri = Uri.parse("package:com.noconnection4629.drimesyncunofficial")
                        intent.setData(uri)
                        self.app._impl.native.startActivity(intent)
                    except Exception as e:
                        print(f"Erreur ouverture directe: {e}")
                        intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                        self.app._impl.native.startActivity(intent)
            else:
                 self.app.main_window.info_dialog("Pas nécessaire", "Android < 11 : Permission spéciale non requise.")

        except Exception as e:
            self.app.main_window.error_dialog("Erreur Technique", f"Impossible d'ouvrir les paramètres : {str(e)}")

    def action_ignore_battery(self, widget):
        if toga.platform.current_platform != 'android': return
        
        success, msg = request_ignore_battery_optimizations_intent()
        if not success:
            self.app.main_window.error_dialog("Erreur Batterie", f"Impossible de lancer la demande : {msg}")
        else:
            pass
