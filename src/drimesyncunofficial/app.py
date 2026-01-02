import asyncio
import toga
import sys
import json
import os
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import (
    API_BASE_URL, HTTP_TIMEOUT, COL_VERT, COL_BLEU, COL_BLEU2, COL_JAUNE, COL_ROUGE, 
    COL_VIOLET, COL_VIOLET2, COL_GRIS, COL_TEXT_GRIS,
    CONF_KEY_API_KEY, CONF_KEY_2FA_SECRET, CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD,
    CONF_KEY_USE_EXCLUSIONS, CONF_KEY_DEBUG_MODE, CONF_KEY_WORKERS, CONF_KEY_SEMAPHORES
)
from drimesyncunofficial.i18n import tr
from drimesyncunofficial.utils import prevent_windows_sleep, get_secure_secret, verify_2fa_code
from drimesyncunofficial.api_client import DrimeAPIClient
from drimesyncunofficial.configuration import ConfigManager
from drimesyncunofficial.trash import TrashManager
from drimesyncunofficial.explorer import ExplorerManager
from drimesyncunofficial.uploads_menu import UploadsMenu
from drimesyncunofficial.downloads_menu import DownloadsMenu
from drimesyncunofficial.share import ShareManager
from drimesyncunofficial.filigranage import WatermarkManager
class DrimeSyncUnofficial(toga.App):
    def __init__(self):
        super().__init__(
            formal_name="Synchronisation avec Drime (non officiel)",
            app_id="com.NoConnection4629.drimesync",
            app_name="drimesyncunofficial",
            version="1.4.0",
            author="NoConnection4629",
            description="Application pour la gestion de la synchronisation avec Drime",
            home_page="https://www.reddit.com/user/No_Connection_4629/"
        )

    def startup(self):
        """
        Point d'entrée principal de l'application Toga.
        Initialise la configuration, le client API et détermine l'écran de démarrage (Login 2FA ou App).
        """
        self.is_mobile = toga.platform.current_platform in {'android', 'iOS'}
        self.navigation_stack = []
        self.workspace_list_cache = [] 
                                    
        self.config_path = self.paths.data / "config.json"
                                             
        self.config_data = self.charger_config()
        
        from drimesyncunofficial.i18n import _i18n_instance
        from drimesyncunofficial.constants import CONF_KEY_LANGUAGE
        saved_lang = self.config_data.get(CONF_KEY_LANGUAGE)
        _i18n_instance.detect_language(forced_lang=saved_lang)

        self.api_client = DrimeAPIClient(self.config_data.get(CONF_KEY_API_KEY, ''))
        if self.config_data.get('prevent_sleep', True):
            prevent_windows_sleep()
        self.main_window = toga.MainWindow(title="DrimeSync Unofficial")
        secret_2fa = get_secure_secret(CONF_KEY_2FA_SECRET) or self.config_data.get(CONF_KEY_2FA_SECRET, '')
        if secret_2fa:
            self.show_login_screen()
        else:
            self.show_main_app()
            self.on_running = self.start_background_checks
        self.main_window.show()
    def changer_ecran(self, nouvelle_box):
        """
        Remplace le contenu de la fenêtre principale par une nouvelle boîte.
        Sauvegarde l'écran actuel dans la pile de navigation.
        """
        if self.main_window.content:
            self.navigation_stack.append(self.main_window.content)
        self.main_window.content = nouvelle_box
    def retour_arriere(self, widget):
        """
        Revient à l'écran précédent dans la pile de navigation.
        """
        if self.navigation_stack:
            dernier_ecran = self.navigation_stack.pop()
            self.main_window.content = dernier_ecran
        else:
            pass
    def show_login_screen(self):
        """Affiche l'écran de verrouillage demandant le code TOTP (2FA)."""
        box = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, margin=20))
        box.add(toga.Label("🔐", style=Pack(font_size=40, margin_bottom=10)))
        box.add(toga.Label(tr("app_locked", "Application Verrouillée"), style=Pack(font_weight=BOLD, font_size=15, margin_bottom=20)))
        box.add(toga.Label(tr("enter_2fa", "Veuillez entrer votre c ode 2FA:"), style=Pack(margin_bottom=10)))
        self.input_2fa_code = toga.TextInput(placeholder="000000", style=Pack(width=150, text_align='center', font_size=20, margin_bottom=20))
        box.add(self.input_2fa_code)
        btn_unlock = toga.Button(tr("unlock_btn", "DEVEROUILLER"), on_press=self.action_unlock_2fa, style=Pack(background_color=COL_VERT, color='white', font_weight=BOLD, width=200, height=50))
        box.add(btn_unlock)
        self.main_window.content = box
    async def action_unlock_2fa(self, widget):
        """Valide le code TOTP saisi par l'utilisateur."""
        code = self.input_2fa_code.value.strip()
        secret = get_secure_secret(CONF_KEY_2FA_SECRET) or self.config_data.get(CONF_KEY_2FA_SECRET, '')
        if verify_2fa_code(secret, code):
            self.show_main_app()
            asyncio.create_task(self.start_background_checks(self))
        else:
            await self.main_window.dialog(toga.ErrorDialog(tr("title_error", "Erreur"), tr("sec_error_2fa", "Code 2FA incorrect.")))
            self.input_2fa_code.value = ""
    def show_main_app(self):
        """Construit et affiche le tableau de bord principal de l'application."""
        main_box = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, margin=15))
        lbl_title = toga.Label('DrimeSync Unofficial', style=Pack(font_size=25, font_weight=BOLD, color=COL_VERT, text_align='center'))
        lbl_version = toga.Label(f'{tr("lbl_version", "Version")} {self.version}', style=Pack(font_size=10, text_align='center', color='gray'))
        lbl_disclaimer = toga.Label(
            tr("disclaimer_text", 'Application non officielle développée par Didier50 (discord) - No_Connection_4629 (reddit)'), 
            style=Pack(font_size=8, text_align='center', color=COL_ROUGE, margin_bottom=10)
        )
        self.lbl_status = toga.Label(tr("init_status", "Initialisation..."), style=Pack(font_size=12, text_align='center', margin_bottom=20, font_weight=BOLD))
        main_box.add(lbl_title); main_box.add(lbl_version); main_box.add(lbl_disclaimer); main_box.add(self.lbl_status)
        btn_style = Pack(font_weight=BOLD, width=300, height=50, margin=5)
        main_box.add(toga.Button(tr("btn_uploads", "📤 UPLOADS"), on_press=self.open_uploads, style=Pack(background_color=COL_VERT, color='white', **btn_style)))
        main_box.add(toga.Button(tr("btn_downloads", "📥 DOWNLOADS"), on_press=self.open_downloads, style=Pack(background_color=COL_BLEU, color='white', **btn_style)))
        main_box.add(toga.Button(tr("btn_share", "🔗 PARTAGE"), on_press=self.open_share, style=Pack(background_color=COL_VIOLET2, color='white', **btn_style)))
        main_box.add(toga.Button(tr("btn_explorer", "📂 EXPLORER"), on_press=self.open_explorer, style=Pack(background_color=COL_JAUNE, color='white', **btn_style)))
        main_box.add(toga.Button(tr("btn_trash", "🗑 CORBEILLE"), on_press=self.open_trash, style=Pack(background_color=COL_ROUGE, color='white', **btn_style)))
        main_box.add(toga.Button(tr("btn_watermark", "🔒 FILIGRANAGE SÉCURISÉ"), on_press=self.open_watermark, style=Pack(background_color=COL_BLEU2, color='white', **btn_style)))
        footer_box = toga.Box(style=Pack(direction=ROW, margin_top=30, width=300))
        footer_box.add(toga.Button(tr("btn_config", "⚙ Config"), on_press=self.open_config, style=Pack(background_color=COL_VIOLET, color='white', flex=1, margin_right=5, height=40)))
        footer_box.add(toga.Button(tr("menu_quit", "Quitter"), on_press=self.action_quitter, style=Pack(background_color=COL_GRIS, color=COL_TEXT_GRIS, flex=1, margin_left=5, height=40)))
        main_box.add(footer_box)
        
        if toga.platform.current_platform == 'android':
             pass                                               
        self.main_window.content = main_box
    async def start_background_checks(self, app):
        """Lance les vérifications asynchrones au démarrage (ex: validité API)."""
        await self.verify_api_startup()
    def open_config(self, widget): ConfigManager(self).show()
    def open_trash(self, widget): TrashManager(self).show()
    def open_explorer(self, widget): ExplorerManager(self).show()
    def open_uploads(self, widget): UploadsMenu(self).show()
    def open_downloads(self, widget): DownloadsMenu(self).show()
    def open_share(self, widget): 
        try:
            ShareManager(self).show()
        except Exception as e:
            import traceback
            traceback.print_exc()
            err_msg = str(e)
            async def _show_err():
                await self.main_window.dialog(toga.ErrorDialog("Erreur", f"Impossible d'ouvrir le menu Partage : {err_msg}"))
            self.loop.create_task(_show_err())
    def open_watermark(self, widget): WatermarkManager(self).show()
    def action_quitter(self, widget):
        self.exit()
        if toga.platform.current_platform == 'android':
            sys.exit(0)
    def charger_config(self):
        """
        Charge la configuration depuis le fichier JSON et le Keyring système.
        Priorité : Keyring (Secrets) > JSON (Config) > Défauts.
        """
        default_config = {
            CONF_KEY_API_KEY: "",
            "workspace_standard_id": "0",
            "workspace_e2ee_id": "0",
            "folder_standard_path": "",
            "folder_e2ee_path": "",
            CONF_KEY_ENCRYPTION_MODE: "NO_ENC",
            CONF_KEY_E2EE_PASSWORD: "",
            CONF_KEY_2FA_SECRET: "",
            CONF_KEY_USE_EXCLUSIONS: True,
            "prevent_sleep": True,
            "download_folder_workspace": "", "download_folder_manual": "",
            "theme": "system", CONF_KEY_WORKERS: 5, CONF_KEY_SEMAPHORES: 0,
            CONF_KEY_DEBUG_MODE: False
        }
        config = default_config.copy()
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f: 
                    loaded = json.load(f)
                    if 'workspace' in loaded and 'workspace_standard_id' not in loaded:
                        loaded['workspace_standard_id'] = loaded['workspace']
                    if 'folder' in loaded and 'folder_standard_path' not in loaded:
                        loaded['folder_standard_path'] = loaded['folder']
                    config.update(loaded)
            except: pass
        secure_api = get_secure_secret(CONF_KEY_API_KEY)
        if secure_api: config[CONF_KEY_API_KEY] = secure_api
        secure_pass = get_secure_secret(CONF_KEY_E2EE_PASSWORD)
        if secure_pass: config[CONF_KEY_E2EE_PASSWORD] = secure_pass
        secure_2fa = get_secure_secret(CONF_KEY_2FA_SECRET)      
        if secure_2fa: config[CONF_KEY_2FA_SECRET] = secure_2fa  
        return config
    async def verify_api_startup(self, widget=None):
        """Vérifie la validité de la clé API et récupère les infos utilisateur."""
        api_key = self.config_data.get(CONF_KEY_API_KEY)
        if not api_key: 
            self.lbl_status.text = tr("status_key_missing", "Clé API manquante")
            return
        loop = asyncio.get_running_loop()
        try:
            def do_req(): return self.api_client.get_logged_user()
            res = await loop.run_in_executor(None, do_req)
            is_success = False
            if isinstance(res, dict):
                if isinstance(res.get('user'), dict): is_success = True
            if is_success:
                email = res['user'].get('email', 'Utilisateur')
                self.lbl_status.text = f"{tr('status_connected', 'Connecté: ')}{email}"
                self.lbl_status.style.color = COL_VERT
                def do_ws(): return self.api_client.get_my_workspaces()
                ws_res = await loop.run_in_executor(None, do_ws)
                if ws_res and isinstance(ws_res.get('workspaces'), list): self.workspace_list_cache = ws_res['workspaces']
            else: 
                self.lbl_status.text = tr("status_key_invalid", "Clé invalide ou erreur API")
                self.lbl_status.style.color = 'red'
        except Exception as e:
            self.lbl_status.text = f"{tr('api_err_network_unexpected', 'Erreur réseau: ')}{e}"

def main():
    return DrimeSyncUnofficial()