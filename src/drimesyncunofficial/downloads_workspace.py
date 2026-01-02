from drimesyncunofficial.base_download_manager import BaseDownloadManager
from drimesyncunofficial.constants import COL_BLEU, ANDROID_DOWNLOAD_PATH
from drimesyncunofficial.browsers import AndroidFileBrowser
from typing import Optional, List, Dict, Any
import toga
import asyncio
from drimesyncunofficial.i18n import tr

class WorkspaceDownloadManager(BaseDownloadManager):
    def show(self) -> None:
        super()._init_ui(title=tr("dl_std_workspace_title", "DOWNLOAD STANDARD (WORKSPACE)"), title_color=COL_BLEU)
        if self.btn_action_main:
             self.btn_action_main.text = tr("btn_download_all", "⬇️ TÉLÉCHARGER TOUT")

    def action_download_main(self, widget):
        """Télécharge tout le contenu affiché (Racine du workspace)."""
        if not self.files_cache:
             self.app.main_window.dialog(toga.InfoDialog(tr("title_info", "Info"), tr("msg_nothing_to_dl", "Rien à télécharger.")))
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
        """Override pour créer un sous-dossier au nom du workspace."""
        if not selection: selection = self.files_cache
        
        if not target_folder:
            if not self.app.is_mobile:
                path = await self.app.main_window.dialog(toga.SelectFolderDialog(tr("title_destination_folder", "Dossier de destination")))
                if not path: return
                target_folder = str(path)
            else:
                target_folder = ANDROID_DOWNLOAD_PATH
        
        ws_id = self._get_ws_id()
        folder_name = f"Workspace_{ws_id}"
        
        if getattr(self.app, 'workspace_list_cache', None):
             for ws in self.app.workspace_list_cache:
                  if str(ws.get('id', '')) == str(ws_id):
                       raw_name = ws.get('label') or ws.get('name')
                       if raw_name:
                            import re
                            clean_name = re.sub(r'[<>:"/\\|?*]', '_', raw_name)
                            folder_name = f"{clean_name}_id_{ws_id}"
                       break
        
        import os
        final_target = os.path.join(target_folder, folder_name)
        await super().start_download(final_target, selection)