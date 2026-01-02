import asyncio
import toga
from typing import Any, Optional, List, Dict
from drimesyncunofficial.downloads_manual_e2ee import ManualDownloadE2EEManager
from drimesyncunofficial.constants import (
    COL_VERT, MODE_NO_ENC, MODE_E2EE_STANDARD,
    CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD, ANDROID_DOWNLOAD_PATH
)
from drimesyncunofficial.utils import generate_or_load_salt, derive_key
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.i18n import tr

class WorkspaceDownloadE2EEManager(ManualDownloadE2EEManager):
    def show(self) -> None:
        try:
            self.app.config_data = self.app.charger_config()
            self.e2ee_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
            self.e2ee_password = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
            if self.e2ee_mode == MODE_NO_ENC: self.e2ee_mode = MODE_E2EE_STANDARD
        except: pass

        if not self.e2ee_password:
             self.app.main_window.dialog(toga.ErrorDialog(tr("sec_2fa_config_req", "Configuration Requise"), tr("err_pwd_missing", "Mot de passe E2EE manquant.")))
             return
        
        try:
             salt = generate_or_load_salt(self.app.paths)
             if not salt:
                 self.app.main_window.dialog(toga.ErrorDialog(tr("sec_err_salt_missing", "Erreur Sel"), tr("err_salt_missing", "Impossible de charger le sel.")))
                 return
             self.e2ee_key = derive_key(str(self.e2ee_password), salt)
        except Exception as e:
             self.app.main_window.dialog(toga.ErrorDialog(tr("sec_err_key", "Erreur Clé"), f"{tr('sec_err_detail', 'Détail')}: {e}"))
             return

        self._init_ui(title=tr("dl_workspace_e2ee_title", "DOWNLOAD E2EE (WORKSPACE)"), title_color=COL_VERT)
        
        if self.btn_action_main:
             self.btn_action_main.text = tr("dl_btn_download_all", "⬇️ TÉLÉCHARGER TOUT")

    def action_download_main(self, widget):
        """Télécharge tout le contenu (Racine)."""
        if not self.files_cache:
             self.app.main_window.dialog(toga.InfoDialog(tr("title_info", "Info"), tr("dl_nothing_to_download", "Rien à télécharger.")))
             return
        
        selection = self.files_cache
        
        if self.app.is_mobile:
            def on_folder_picked(result_path):
                self.app.main_window.content = self.main_box_content
                if result_path:
                    asyncio.create_task(self.start_download(str(result_path), selection=selection))
                else:
                    self.log_ui(tr("log_selection_cancelled", "Sélection annulée."), "yellow")
            
            browser = AndroidFileBrowser(self.app, on_folder_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
            self.app.main_window.content = browser
        else:
            asyncio.create_task(self.start_download(selection=selection))

    async def start_download(self, target_folder: Optional[str] = None, selection: List[Dict[str, Any]] = None):
        """Override pour créer un sous-dossier au nom du workspace (E2EE)."""
        if not selection: selection = self.files_cache
        
        if not target_folder:
            if not self.app.is_mobile:
                path = await self.app.main_window.dialog(toga.SelectFolderDialog(tr("title_destination_folder", "Dossier de destination")))
                if not path: return
                target_folder = str(path)
            else:
                target_folder = ANDROID_DOWNLOAD_PATH
        
        ws_id = self.app.config_data.get('workspace_e2ee_id', '0')
        folder_name = f"Workspace_E2EE_{ws_id}"
        
        if getattr(self.app, 'workspace_list_cache', None):
             for ws in self.app.workspace_list_cache:
                  if str(ws.get('id', '')) == str(ws_id):
                       raw_name = ws.get('label') or ws.get('name')
                       if raw_name:
                            import re
                            clean_name = re.sub(r'[<>:"/\\|?*]', '_', raw_name)
                            folder_name = f"{clean_name}_id_{ws_id}_E2EE"
                       break
        
        import os
        final_target = os.path.join(target_folder, folder_name)
        await super().start_download(final_target, selection)