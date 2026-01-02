import toga
import json
import asyncio
import os
from pathlib import Path
import time
import math
import mimetypes
import hashlib
import threading
import re
import fnmatch
import tempfile
from io import BytesIO
from queue import Queue
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable, Set, Tuple
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import (
    COL_GRIS, COL_TEXT_GRIS, COL_VERT, COL_ROUGE, COL_JAUNE, COL_BLEU, COL_VIOLET, COL_BLEU2, 
    API_BASE_URL, HTTP_TIMEOUT, SYNC_STATE_FOLDER_NAME, CLOUD_TREE_FILE_NAME, EXCLUDE_FILE_NAME, 
    PARTIAL_HASH_CHUNK_SIZE,
    CONF_KEY_API_KEY, CONF_KEY_WORKERS, CONF_KEY_SEMAPHORES, CONF_KEY_USE_EXCLUSIONS,
    ANDROID_DOWNLOAD_PATH
)
from drimesyncunofficial.api_client import DrimeClientError
from drimesyncunofficial.utils import format_size, load_exclusion_patterns, truncate_path_smart, sanitize_filename_for_upload
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.base_transfer_manager import BaseTransferManager
from drimesyncunofficial.i18n import tr

SYNC_STATE_FOLDER = SYNC_STATE_FOLDER_NAME
CLOUD_TREE_FILE = CLOUD_TREE_FILE_NAME

CHUNK_SIZE = 25 * 1024 * 1024
BATCH_SIZE = 10
PART_UPLOAD_RETRIES = 10
MULTIPART_THRESHOLD = 30 * 1024 * 1024

class MirrorUploadManager(BaseTransferManager):
    """
    Gestionnaire de Synchronisation Miroir (Mode Standard).
    Synchronise un dossier local vers un workspace distant.
    """
    def __init__(self, app: Any):
        super().__init__(app)
        self.mirror_local_path: str = self.app.config_data.get('folder_standard_path', '')
        
                                             
        self.lbl_warning_ws: Optional[toga.Label] = None
        self.lbl_conflict_warning: Optional[toga.Label] = None
        self.btn_sync: Optional[toga.Button] = None
        self.btn_simu: Optional[toga.Button] = None
        self.btn_force: Optional[toga.Button] = None
        self.box_secondary_btns: Optional[toga.Box] = None
        self.txt_logs: Optional[toga.MultilineTextInput] = None
        self.selection_mirror_ws: Optional[toga.Selection] = None
        self.lbl_mirror_path: Optional[toga.Label] = None
        self.main_box_content = None

                                    
        self.simple_upload_limiter: Optional[threading.Semaphore] = None
        self.total_size: int = 0
        self.total_transferred: int = 0
        self.progress_lock: threading.Lock = threading.Lock()

    def show(self) -> None:
        """Affiche l'interface de configuration du miroir Standard."""
        self.app.config_data = self.app.charger_config()
        
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))
        
                  
        box.add(create_back_button(self.go_back, margin_bottom=20))
        box.add(toga.Label(tr("up_mirror_title_std", "--- MODE STANDARD ---"), style=Pack(font_weight=BOLD, color=COL_BLEU, margin_bottom=5, font_size=12)))
        box.add(toga.Label(tr("up_mirror_subtitle_std", "Synchronisation en clair (Noms et Contenus visibles)"), style=Pack(font_size=10, margin_bottom=20, color=COL_TEXT_GRIS)))
        
                           
        box.add(toga.Label(tr("lbl_source", "Source (Dossier Local) :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.lbl_mirror_path = toga.Label(self.mirror_local_path or "Aucun dossier choisi", style=Pack(margin_bottom=5, color='gray', flex=1))
        box.add(self.lbl_mirror_path)
        box.add(toga.Button(tr("up_btn_choose_folder", "📂 Choisir le dossier..."), on_press=self.action_mirror_choose_folder, style=Pack(margin_bottom=20, flex=1)))
        
                                
        box.add(toga.Label(tr("lbl_destination", "Destination (Workspace) :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        items = ["Espace Personnel (ID: 0)"]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: items.append(f"{ws['name']} (ID: {ws['id']})")
            
        self.selection_mirror_ws = toga.Selection(items=items, on_change=self.update_warnings, style=Pack(width=220, margin_bottom=10))
        current_saved_ws_id = self.app.config_data.get('workspace_standard_id', '0')
        selected_item_str = next((item for item in items if f"(ID: {current_saved_ws_id})" in item), items[0])
        self.selection_mirror_ws.value = selected_item_str
        box.add(self.selection_mirror_ws)
        
                         
                         
        self.lbl_warning_ws = toga.Label(tr("up_warn_mirror_ws", "⚠️ Déconseillé dans l'Espace Personnel.\\nCréez un workspace dédié."), style=Pack(font_size=8, color=COL_ROUGE, font_weight=BOLD, margin_bottom=10, visibility='hidden', flex=1))
        box.add(self.lbl_warning_ws)
        self.lbl_conflict_warning = toga.Label(tr("warn_conflict_mirror", "⚠️ CONFLIT : Workspace utilisé par le\\nmiroir CHIFFRÉ. Risque de désynchronisation."), style=Pack(font_size=8, color=COL_JAUNE, font_weight=BOLD, margin_bottom=20, visibility='hidden', flex=1))
        box.add(self.lbl_conflict_warning)
        
                                             
        self.btn_sync = toga.Button("🟦 SYNCHRONISER (STANDARD)", on_press=self.action_mirror_sync_wrapper, style=Pack(height=50, background_color=COL_BLEU, color='white', font_weight=BOLD, flex=1))
        box.add(self.btn_sync)
        
        self.box_secondary_btns = toga.Box(style=Pack(direction=ROW, margin_top=5, flex=1))
        self.btn_simu = toga.Button(tr("btn_simulation", "Simulation"), on_press=self.action_mirror_simu_wrapper, style=Pack(flex=1, margin_right=5, height=40, background_color=COL_JAUNE, color='white'))
        self.btn_force = toga.Button(tr("btn_force_sync", "Synchro Forcée"), on_press=self.action_mirror_force_wrapper, style=Pack(flex=1, margin_left=5, height=40, background_color=COL_GRIS, color=COL_ROUGE, font_weight=BOLD))
        self.box_secondary_btns.add(self.btn_simu)
        self.box_secondary_btns.add(self.btn_force)
        box.add(self.box_secondary_btns)
        
                                                                   
        self.box_controls = toga.Box(style=Pack(direction=ROW, visibility='hidden', height=0, flex=1))
        self.btn_pause = toga.Button(tr("btn_pause", "⏸️ Pause"), on_press=self.action_toggle_pause, style=Pack(flex=1, margin_right=5, height=50, background_color=COL_JAUNE, color='white', visibility='hidden'))
        self.btn_cancel = toga.Button(tr("btn_cancel_all", "⏹️ Annuler Tout"), on_press=self.action_cancel, style=Pack(flex=1, margin_left=5, height=50, background_color=COL_ROUGE, color='white', font_weight=BOLD, visibility='hidden'))
        self.box_controls.add(self.btn_pause)
        self.box_controls.add(self.btn_cancel)
        box.add(self.box_controls)
        
        box.add(toga.Divider(style=Pack(margin_top=15, margin_bottom=10)))
        
                                       
        self.lbl_progress = toga.Label("", style=Pack(font_weight=BOLD, margin_bottom=5, font_size=10, color=COL_JAUNE, flex=1))
        box.add(self.lbl_progress)
        
        box.add(self.lbl_progress)
        
        box.add(toga.Label(tr("lbl_log", "Log :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.txt_logs = create_logs_box(height=150, margin=5)
                                                                   
        self.log_output = self.txt_logs 
        box.add(self.txt_logs)
        
        self.update_warnings(None)
        
                                                                       
        self._set_ui_running(False)
        
        main_container.content = box
        self.main_box_content = main_container 
        self.app.changer_ecran(main_container)

    def _set_ui_running(self, running: bool) -> None:
        """Bascule l'interface (Override manuel comme E2EE pour éviter les glitches)."""
        self.is_running = running
        if running:
            self.stop_event.clear()
            self.is_cancelled = False
            self.is_paused = False
        
        def _update():
            if running:
                self.btn_sync.style.visibility = 'hidden'; self.btn_sync.style.height = 0; self.btn_sync.style.margin_bottom = 0
                self.box_secondary_btns.style.visibility = 'hidden'; self.box_secondary_btns.style.height = 0; self.box_secondary_btns.style.margin_bottom = 0
                
                self.box_controls.style.visibility = 'visible'; self.box_controls.style.height = 50
                self.btn_pause.style.visibility = 'visible'; self.btn_pause.style.height = 50
                self.btn_pause.style.margin_right = 5
                
                self.btn_cancel.style.visibility = 'visible'; self.btn_cancel.style.height = 50
                self.btn_cancel.style.margin_left = 5
                
                self.btn_pause.enabled = True; self.btn_cancel.enabled = True
                self.btn_pause.text = tr("btn_pause", "⏸️ Pause"); self.btn_pause.style.background_color = COL_JAUNE
            else:
                self.box_controls.style.visibility = 'hidden'; self.box_controls.style.height = 0
                self.btn_pause.style.visibility = 'hidden'; self.btn_pause.style.height = 0
                self.btn_cancel.style.visibility = 'hidden'; self.btn_cancel.style.height = 0
                
                self.btn_sync.style.visibility = 'visible'; self.btn_sync.style.height = 50; self.btn_sync.style.margin_bottom = 5
                self.box_secondary_btns.style.visibility = 'visible'; self.box_secondary_btns.style.height = 40; self.box_secondary_btns.style.margin_bottom = 5
                
                self.btn_simu.enabled = True; self.btn_sync.enabled = True; self.btn_force.enabled = True
                
                if self.lbl_progress:
                     final_text = "Terminé (Standard)." if not self.is_cancelled else "Annulé."
                     self.lbl_progress.text = final_text
                     self.lbl_progress.style.color = COL_VERT if not self.is_cancelled else COL_ROUGE
                     
            if hasattr(self.app.main_window, 'content'):
                self.app.main_window.content.refresh()
        self.app.loop.call_soon_threadsafe(_update)

    def update_warnings(self, widget: Any) -> None:
        if not self.lbl_warning_ws: return
        sel = self._get_selected_workspace_id()
        e2ee_id = self.app.config_data.get('workspace_e2ee_id', '0')
        if sel == '0': self.lbl_warning_ws.style.visibility = 'visible'
        else: self.lbl_warning_ws.style.visibility = 'hidden'
        if sel == e2ee_id: self.lbl_conflict_warning.style.visibility = 'visible'
        else: self.lbl_conflict_warning.style.visibility = 'hidden'

    def go_back(self, widget: Any) -> None:
        if self.is_running: return
        self.app.retour_arriere(widget)

    def _get_selected_workspace_id(self) -> Optional[str]:
        val = self.selection_mirror_ws.value
        if "ID: 0" in val: return "0"
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return None

    def action_mirror_choose_folder(self, widget: Any) -> None:
        """Déclenche la sélection de dossier. Sur Android, utilise le navigateur interne."""
        if self.app.is_mobile:
            def on_folder_picked(result_path):
                self.app.main_window.content = self.main_box_content
                if result_path:
                    self.mirror_local_path = str(result_path)
                    self.lbl_mirror_path.text = self.mirror_local_path
                    self.app.config_data['folder_standard_path'] = self.mirror_local_path
                    self._save_config_file()
                    self.log_ui(f"Dossier défini : {result_path}", "green")
                else:
                    self.log_ui("Sélection annulée.", "yellow")
            browser = AndroidFileBrowser(self.app, on_folder_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
            self.app.main_window.content = browser
        else:
            self.action_mirror_choose_folder_desktop(widget)

    def action_mirror_choose_folder_desktop(self, widget):
        async def _ask():
            path = await self.app.main_window.dialog(toga.SelectFolderDialog("Choisir dossier source"))
            if path:
                self.mirror_local_path = str(path)
                self.lbl_mirror_path.text = self.mirror_local_path
                self.app.config_data['folder_standard_path'] = self.mirror_local_path
                self._save_config_file()
        asyncio.ensure_future(_ask())

    def _save_config_file(self) -> None:
        self.app.config_data['workspace_standard_id'] = self._get_selected_workspace_id()
        config_to_save = self.app.config_data.copy()
        is_desktop = toga.platform.current_platform not in {'android', 'iOS', 'web'}
        if is_desktop:
            config_to_save['api_key'] = ""
            config_to_save['e2ee_password'] = ""
            config_to_save['2fa_secret'] = ""
        try:
            with open(self.app.config_path, 'w', encoding='utf-8') as f: 
                json.dump(config_to_save, f, indent=4)
        except: pass

    async def action_cancel(self, widget: Any) -> None:
        """Surcharge pour demander confirmation avant annulation."""
        if not self.is_running: return
        if await self.app.main_window.dialog(toga.QuestionDialog(tr("title_confirmation", "Confirmation"), tr("msg_cancel_sync", "Voulez-vous vraiment annuler la synchronisation ?"))):
           super().action_cancel(widget)

    async def action_mirror_simu_wrapper(self, widget: Any) -> None:
        await self.launch_sync_thread(is_dry_run=True)

    async def action_mirror_sync_wrapper(self, widget: Any) -> None:
        await self.launch_sync_thread(is_dry_run=False)

    async def action_mirror_force_wrapper(self, widget: Any) -> None:
        if await self.app.main_window.dialog(toga.QuestionDialog("DANGER", "Cette action va EFFACER tout le contenu du Workspace distant et tout ré-uploader.\n\nContinuer ?")):
            await self.launch_sync_thread(is_dry_run=False, force_sync=True)

    async def launch_sync_thread(self, is_dry_run: bool, force_sync: bool = False) -> None:
        if self.is_running: return
        if not self.mirror_local_path or not os.path.exists(self.mirror_local_path):
             await self.app.main_window.dialog(toga.ErrorDialog(tr("title_error", "Erreur"), tr("err_local_folder_missing", "Dossier local manquant.")))
             return
        
        self._save_config_file()
        self.stop_event.clear()
        self.txt_logs.value = ""
        self.lbl_progress.text = ""
        
                            
        self._set_ui_running(True)
        self.update_status_ui("Préparation...", COL_JAUNE)
        
                              
        run_in_background(self._spinner_loop)
        
                                   
                                                                                                          
        t = run_in_background(
            self._thread_mirror_logic, 
            self.mirror_local_path, 
            self._get_selected_workspace_id(), 
            is_dry_run, 
            force_sync
        )
        t.name = "Thread-Mirror-Logic"

    def _spinner_loop(self):
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        idx = 0
        while self.is_running and not self.stop_event.is_set():
            if not self.is_paused:
                txt = getattr(self, 'last_text', '')
                if txt and "Terminé" not in txt:
                    char = chars[idx % len(chars)]
                    idx += 1
                    char = chars[idx % len(chars)]
                    idx += 1
                    safe_update_label(self.app, self.lbl_progress, f"{txt}   {char}")
            time.sleep(0.1)

    def _get_local_state_dir(self, workspace_id: str) -> str:
        ws_name = "Workspace"
        if workspace_id == "0": ws_name = "Espace_Personnel"
        else:
            for w in self.app.workspace_list_cache:
                if str(w.get('id')) == str(workspace_id): ws_name = w.get('name', 'Inconnu'); break
        safe_name = "".join([c for c in ws_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        folder_name = f"{safe_name}_{workspace_id}_STD" 
        state_dir = self.app.paths.data / "MirrorStates" / folder_name
        if not state_dir.exists(): state_dir.mkdir(parents=True, exist_ok=True)
        return str(state_dir)

    def _calculate_remote_path(self, rel_path: str, is_folder: bool = False) -> str:
        path = rel_path.replace("\\", "/")
        parts = path.split("/")
                                                                                   
        new_parts = [sanitize_filename_for_upload(p) for p in parts]
        new_path = "/".join(new_parts)
        if new_path != path:
             self.log_ui(f"[yellow]Contournement bug '0': {path} -> {new_path}[/yellow]")
        return new_path

    def delete_all_cloud_content(self, api_key: str, workspace_id: str) -> bool:
        """Supprime tout le contenu distant (pour la synchro forcée)."""
        self.log_ui("[red]MODE FORCE-SYNC : SUPPRESSION TOTALE...[/red]")
        params = {}
        if workspace_id != "0": params['workspaceId'] = workspace_id
        try:
                                                      
            all_ids = []
            page = 1
            while True:
                 params['page'] = page
                 self.log_ui(f"[DEBUG] Listing page {page}...")
                 try:
                                                                    
                     data = self.app.api_client.list_files(params=params)
                 except Exception as e:
                     self.log_ui(f"[red]Erreur listing: {e}[/red]")
                     return False
                 
                 if not data or 'data' not in data: break
                 items = data['data']
                 if not items: break
                 for item in items: all_ids.append(str(item['id']))
                 
                 if len(items) < 20: break 
                 page += 1
            
            if not all_ids: return True

            self.log_ui(f"Suppression de {len(all_ids)} éléments...")
            
                                                                       
            total = len(all_ids)
            batch_size = 50
            timeout_val = None
            
            if self.app.is_mobile:
                batch_size = 20
                timeout_val = 60
                
            for i in range(0, total, batch_size):
                if self.stop_event.is_set(): return False
                batch = all_ids[i:i+batch_size]
                
                kwargs = {}
                if timeout_val: kwargs['timeout'] = timeout_val
                
                self.app.api_client.delete_entries(entry_ids=batch, delete_forever=True, **kwargs)
                self.log_ui(f'''{tr('log_batch_delete', "Lot d'éléments supprimés...")} ({len(batch)}) ({min(i+batch_size, total)}/{total})''')
                time.sleep(0.1)

            self.log_ui(f"[green]{tr('log_cloud_emptied', 'Cloud vidé.')}[/green]")
            return True
        except Exception as e:
            self.log_ui(f"{tr('error_delete_all', 'Erreur delete_all:')} {e}", "red")
            return False

    def get_partial_hash(self, file_path: str, file_size: int) -> Optional[str]:
        m = hashlib.md5()
        m.update(str(file_size).encode('utf-8'))
        try:
            with open(file_path, "rb") as f:
                if file_size <= PARTIAL_HASH_CHUNK_SIZE * 2: m.update(f.read())
                else:
                    m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
                    f.seek(-PARTIAL_HASH_CHUNK_SIZE, os.SEEK_END)
                    m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
            return m.hexdigest()
        except Exception as e:
            self.log_ui(f"{tr('debug_error_hash', '[DEBUG] Erreur hash')} {file_path}: {e}", "red")
            return None

    def get_local_tree(self, root_folder: str, app_data_state_dir: str, use_exclusions: bool = True) -> Dict[str, Any]:
        self.log_ui(f"{tr('scan_local_folder', 'Scan du dossier local :')} {root_folder}")
        tree = {"folders": set(), "files": {}}
        exclusions = load_exclusion_patterns(self.app.paths, use_exclusions)
        root_path_obj = Path(root_folder)
        for root, dirs, files in os.walk(root_folder):
            if self.stop_event.is_set(): break
            
                                
            for d in dirs[:]:
                full_dir = Path(root) / d
                try:
                    rel = str(full_dir.relative_to(root_path_obj)).replace("\\", "/")
                except ValueError: continue
                if any(fnmatch.fnmatch(rel, p) for p in exclusions): 
                    dirs.remove(d); continue
                tree["folders"].add(rel)
                
                          
            for f in files:
                full = Path(root) / f
                try:
                    rel = str(full.relative_to(root_path_obj)).replace("\\", "/")
                except ValueError: continue
                if any(fnmatch.fnmatch(rel, p) for p in exclusions): continue
                try:
                    st = full.stat()
                    if st.st_size >= 0:
                        ph = self.get_partial_hash(full, st.st_size)
                        if ph: 
                            tree["files"][rel] = {"full_path": str(full), "size": st.st_size, "mtime": st.st_mtime, "partial_hash": ph}
                        else:
                            self.log_ui(f"{tr('debug_hash_failed', '[DEBUG] Hash échoué pour')} {f} -> Ignoré", "yellow")
                except Exception as e:
                    self.log_ui(f"{tr('debug_access_error', '[DEBUG] Erreur accès')} {f}: {e}", "red")
        return tree

    def load_local_cloud_tree(self, app_data_state_dir: str, api_key: str, ws_id: str) -> Dict[str, Any]:
        path = os.path.join(app_data_state_dir, CLOUD_TREE_FILE)
        if not os.path.exists(path):
            self.log_ui(tr("debug_missing_local_state", "[DEBUG] État local manquant. Recherche Recovery..."))
            found_file = None
            resp = self.app.api_client.list_files(params={"query": CLOUD_TREE_FILE, "workspaceId": ws_id})
                                                                                                                                                                     
            data = resp                   
            if data and 'data' in data:
                 for f in data['data']:
                     if f['name'] == CLOUD_TREE_FILE:
                         found_file = f; break
            
            if found_file:
                msg_found = tr('info_state_found', "[INFO] Fichier d'état trouvé. Récupération...")
                self.log_ui(f"{msg_found} (ID: {found_file['id']})")
                try:
                    dl_url = f"{API_BASE_URL}/file-entries/download/{found_file['hash']}"
                                                                 
                    with self.app.api_client.get_download_stream(dl_url) as r:
                         if r.status_code == 200:
                            content = r.content
                            try:
                                json.loads(content)
                                with open(path, 'wb') as f: f.write(content)
                                self.log_ui(tr("success_state_restored", "[SUCCESS] État restauré."), "green")
                            except:
                                self.log_ui(tr("error_state_corrupted", "[ERROR] Fichier trouvé mais corrompu."), "red")
                except Exception as e:
                    self.log_ui(f"{tr('error_recovery_failed', '[ERROR] Recovery failed:')} {e}", "red")
            else:
                self.log_ui(tr("info_no_remote_state", "[INFO] Pas d'état distant. Départ à zéro."), "yellow")
        
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f: return json.load(f)
            except: pass
        return {"folders": {}, "files": {}}

    def save_local_cloud_tree(self, tree: Dict[str, Any], app_data_state_dir: str) -> None:
        path = Path(app_data_state_dir) / CLOUD_TREE_FILE
        try:
            with open(path, 'w', encoding='utf-8') as f: json.dump(tree, f, indent=2)
        except: pass

    def handle_folder_creation(self, rel_folder_path: str, cloud_tree: Dict[str, Any], ws_id: str, is_dry_run: bool) -> None:
        cloud_path = self._calculate_remote_path(rel_folder_path, is_folder=True)
        if rel_folder_path in cloud_tree["folders"]: return
        if "/" in rel_folder_path:
            parent_rel = rel_folder_path.rsplit('/', 1)[0]
            if parent_rel not in cloud_tree["folders"]:
                self.handle_folder_creation(parent_rel, cloud_tree, ws_id, is_dry_run)
            parent_id = cloud_tree["folders"][parent_rel]["id"]
        else: parent_id = ws_id
        
        if is_dry_run:
            self.log_ui(f"{tr('simu_create_folder', '[SIMU] Création dossier:')} {rel_folder_path}")
            cloud_tree["folders"][rel_folder_path] = {"id": f"SIMU_ID_{rel_folder_path}", "name": cloud_path.split("/")[-1]}
            return
            
        folder_name_to_create = cloud_path.split("/")[-1]
        try:
             entry = self.app.api_client.create_folder(name=folder_name_to_create, parent_id=parent_id if parent_id != ws_id else None, workspace_id=ws_id)
             if entry and (entry.get('folder') or entry).get('id'):
                 cloud_tree["folders"][rel_folder_path] = entry.get('folder') or entry
        except DrimeClientError:
                                                 
             l_resp = self.app.api_client.list_files(params={"folderId": parent_id if parent_id != ws_id else None, "workspaceId": ws_id})
                                      
             data = l_resp
             if data and 'data' in data:
                 for i in data['data']:
                     if i['type'] == 'folder' and i['name'] == folder_name_to_create:
                         cloud_tree["folders"][rel_folder_path] = i
                         return
                 self.log_ui(f"{tr('log_folder_created', 'Dossier créé:')} {rel_folder_path}")

    def rename_remote_entry(self, entry_id: str, new_name: str, api_key: str) -> Optional[str]:
        try:
            resp = self.app.api_client.rename_entry(entry_id, new_name)
            if resp.status_code == 200:
                data = resp.json()
                return (data.get('id') or data.get('fileEntry', {}).get('id'))
        except: pass
        return None

    def upload_worker(self, q: Queue, res_q: Queue, api_key: str, ws_id: str) -> None:
        thread_name = threading.current_thread().name
        while True:
            try: item = q.get_nowait()
            except: break
            
            if self.stop_event.is_set(): 
                q.task_done(); continue
            while self.is_paused: time.sleep(0.5)
            
            rel_path, info = item
            remote_path = self._calculate_remote_path(rel_path, is_folder=False)
                                                                                      
            result = None
            try:
                result = self.upload_file_router(info, remote_path, api_key, ws_id, thread_name)
            except Exception as e:
                self.log_ui(f"[{thread_name}] {tr('crash_worker', 'CRASH Worker:')} {e}", "red")
            res_q.put((rel_path, result))
            q.task_done()

    def parse_api_response_for_id(self, response: Any) -> Optional[Dict[str, Any]]:
        if not response: return None
        if isinstance(response, dict) and 'error_code' in response: return None
        if 'fileEntry' in response: return response['fileEntry']
        elif 'id' in response and 'name' in response: return response
        return None

    def upload_file_router(self, local_info: Dict[str, Any], cloud_relative_path: str, api_key: str, workspace_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        file_size = local_info["size"]
        file_name = Path(cloud_relative_path).name
        try:
            if file_size > MULTIPART_THRESHOLD:
                return self.upload_multipart(local_info, cloud_relative_path, api_key, workspace_id, thread_name)
            else:
                with self.simple_upload_limiter:
                    return self.upload_simple(local_info, cloud_relative_path, api_key, workspace_id, thread_name)
        except Exception as e:
            self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_router_error', 'Erreur router')} {file_name}: {e}")
            return None

    def upload_simple(self, local_info: Dict[str, Any], cloud_relative_path: str, api_key: str, workspace_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        file_path = local_info["full_path"]
        file_name = Path(cloud_relative_path).name
        try:
            resp = self.app.api_client.upload_simple(file_path, workspace_id, cloud_relative_path, custom_file_name=file_name)
            if resp.status_code in [200, 201]:
                fe = self.parse_api_response_for_id(resp.json())
                if fe and fe.get('id'):
                    with self.progress_lock:
                        self.total_transferred += local_info["size"]
                        percent = int((self.total_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                        self.update_status_ui(f"Upload {format_size(self.total_transferred)}/{format_size(self.total_size)} {percent}%", COL_BLEU2)
                    return {"id": fe["id"], "size": local_info["size"], "mtime": local_info["mtime"], "partial_hash": local_info["partial_hash"]}
            if resp.status_code == 403:
                self.log_ui(f"[red]{tr('error_403_forbidden', 'ERREUR 403 (Interdit) pour')} {file_name}. Vérifiez vos droits.[/red]")
                return {"error": "403_FORBIDDEN"}
            self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_upload_simple_invalid', 'Réponse upload simple invalide pour')} {file_name}. {resp.text}")
        except Exception as e:
            self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_upload_simple_error', 'Erreur upload simple')} {file_name}: {e}")
        return None

    def upload_multipart(self, local_info: Dict[str, Any], cloud_relative_path: str, api_key: str, workspace_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        file_path = local_info["full_path"]
        file_name = Path(cloud_relative_path).name
        file_size = local_info["size"]
        num_parts = math.ceil(file_size / CHUNK_SIZE)
                                                                                                 
        try:
            init_resp = self.app.api_client.upload_multipart_init(file_name, file_size, cloud_relative_path, workspace_id)
            if init_resp.status_code not in [200, 201]:
                self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_multipart_init_failed', 'Multipart init failed:')} {init_resp.status_code} {init_resp.text}")
                return None
            init_data = init_resp.json()
            if 'uploadId' not in init_data:
                self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_multipart_missing_id', 'Multipart init missing uploadId:')} {init_data}")
                return None
            upload_id = init_data['uploadId']
            key = init_data['key']
            uploaded_parts = []
            
            with open(file_path, "rb") as f:
                part_number = 1
                while part_number <= num_parts:
                    if self.stop_event.is_set(): raise Exception("Cancelled")
                    while self.is_paused: time.sleep(0.5)
                    
                    if self.app.is_mobile: time.sleep(0.005)

                    batch_end = min(part_number + BATCH_SIZE - 1, num_parts)
                    batch_nums = list(range(part_number, batch_end + 1))
                    
                    sign_resp = self.app.api_client.upload_multipart_sign_batch(key, upload_id, batch_nums)
                    if sign_resp.status_code not in [200, 201]:
                        return None
                    sign_data = sign_resp.json()
                    if 'urls' not in sign_data:
                        return None
                    urls_map = {u['partNumber']: u['url'] for u in sign_data['urls']}
                    
                    for pn in batch_nums:
                        if self.app.is_mobile: time.sleep(0.005)
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk: break
                        url = urls_map.get(pn)
                        if not url: return None
                        
                        for attempt in range(PART_UPLOAD_RETRIES):
                            try:
                                r = self.app.api_client.upload_multipart_put_chunk(url, chunk)
                                if r.status_code in [200, 201]:
                                    uploaded_parts.append({"PartNumber": pn, "ETag": r.headers.get("ETag", "").strip('"')})
                                    with self.progress_lock:
                                        self.total_transferred += len(chunk)
                                        percent = int((self.total_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                                        self.update_status_ui(f"Upload {format_size(self.total_transferred)}/{format_size(self.total_size)} {percent}%", COL_BLEU2)
                                    break
                                else:
                                    time.sleep(1 * attempt)
                            except Exception:
                                time.sleep(1 * attempt)
                        else:
                            return None                      
                    part_number += BATCH_SIZE
                    
            comp_resp = self.app.api_client.upload_multipart_complete(key, upload_id, uploaded_parts)
            if comp_resp.status_code not in [200, 201]:
                return None
            
            ext = Path(file_name).suffix.lstrip('.')
            mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            
            entry_data = {
                "clientMime": mime_type, "clientName": file_name,
                "filename": key.split("/")[-1], "size": file_size,
                "clientExtension": ext,
                "relativePath": cloud_relative_path.replace("\\", "/"), "workspaceId": workspace_id
            }
            entry_resp = self.app.api_client.create_entry(entry_data)
            if entry_resp.status_code in [200, 201]:
                 fe = self.parse_api_response_for_id(entry_resp.json())
                 if fe and fe.get('id'):
                     return {"id": fe["id"], "size": file_size, "mtime": local_info["mtime"], "partial_hash": local_info["partial_hash"]}
            return None
        except Exception as e:
            self.log_ui(f"[DEBUG] [{thread_name}] {tr('debug_multipart_error', 'Multipart error:')} {e}")
            return None

    def generate_report(self, stats: Dict[str, Any], duration: float, final_status: str) -> str:
        if duration < 1: duration = 1
        speed = stats['bytes'] / duration
        speed_str = format_size(speed) + "/s"
        return (
            f"{tr('report_mirror_std_title', 'MIROIR STANDARD')} {final_status}\n\n"
            f"✅ {tr('report_success', 'Succès')} : {stats['success']}\n"
            f"✏️ {tr('report_renamed', 'Renommés')} : {stats['renamed']}\n"
            f"🗑️ {tr('report_deleted', 'Supprimés')} : {stats['deleted']}\n"
            f"❌ {tr('report_failures', 'Échecs')} : {stats['failed']}\n\n"
            f"📦 {tr('report_volume', 'Volume')} : {format_size(stats['bytes'])}\n"
            f"⚡ {tr('report_speed', 'Vitesse')} : {speed_str}\n"
            f"⏱️ {tr('report_duration', 'Durée')} : {int(duration)}s"
        )

    def _thread_mirror_logic(self, local_folder: str, workspace_id: str, is_dry_run: bool, force_sync: bool) -> None:
        try:
            start_str = tr("log_start_simu", "--- DÉMARRAGE SIMU ---") if is_dry_run else tr("log_start_std", "--- DÉMARRAGE STANDARD ---")
            self.log_ui(start_str, "green")
            start_time = time.time()
            files_success_count = 0; files_failed_count = 0; files_renamed_count = 0; files_moved_count = 0; files_deleted_count = 0; total_bytes_uploaded = 0
            
            api_key = self.app.config_data.get(CONF_KEY_API_KEY, '')
            nb_workers = int(self.app.config_data.get(CONF_KEY_WORKERS, 5))
            sem_val = int(self.app.config_data.get(CONF_KEY_SEMAPHORES, 0))
            if sem_val == 0: sem_val = nb_workers
            
            self.simple_upload_limiter = threading.Semaphore(sem_val)
            app_data_state_dir = self._get_local_state_dir(workspace_id)
            
            if force_sync and not is_dry_run:
                if not self.delete_all_cloud_content(api_key, workspace_id): return
                path = Path(app_data_state_dir) / CLOUD_TREE_FILE
                if path.exists(): 
                     path.unlink()
                     self.log_ui(tr("log_reset_local_state", "État local réinitialisé."), "yellow")
                     
            cloud_tree = self.load_local_cloud_tree(app_data_state_dir, api_key, workspace_id)
            use_exc = self.app.config_data.get(CONF_KEY_USE_EXCLUSIONS, True)
            local_tree = self.get_local_tree(local_folder, app_data_state_dir, use_exc)
            
            self.log_ui(tr("log_comparing_trees", "Comparaison des arbres..."))
            self.update_status_ui(tr("status_comparing", "Comparaison..."), COL_VERT)
            
                                 
            local_folders = local_tree["folders"]
            cloud_folders = set(cloud_tree["folders"].keys())
            folders_to_create = sorted(local_folders - cloud_folders, key=lambda x: x.count("/"))
            
            for fp in folders_to_create:
                if self.app.is_mobile: time.sleep(0.002)
                if self.stop_event.is_set(): break
                self.handle_folder_creation(fp, cloud_tree, workspace_id, is_dry_run)
                
            folders_to_delete = sorted(cloud_folders - local_folders, key=lambda x: x.count("/"), reverse=True)
            folders_to_delete_ids = []
            for fp in folders_to_delete:
                if fp in cloud_tree["folders"]:
                    folders_to_delete_ids.append(cloud_tree["folders"][fp]["id"])
                    del cloud_tree["folders"][fp]
                    if is_dry_run: self.log_ui(f"{tr('simu_delete_folder', '[SIMU] Suppression dossier:')} {fp}", "red")
                    else: self.log_ui(f"{tr('debug_delete_folder', '[DEBUG] Suppression dossier:')} {fp}")

                                    
            self.log_ui(tr("log_analyzing_files", "Analyse des fichiers..."))
            self.update_status_ui(tr("status_analyzing_files", "Analyse des fichiers..."), COL_VERT)
            
            local_paths = set(local_tree["files"].keys())
            cloud_paths = set(cloud_tree["files"].keys())
            files_to_upload = []
            renamed_in_place = []
            paths_to_upload_later = set(paths_to_add := local_paths - cloud_paths)
            paths_to_delete_later = set(paths_to_delete := cloud_paths - local_paths)
            paths_to_check = local_paths & cloud_paths
            
                            
            local_hashes = {info["partial_hash"]: [] for info in local_tree["files"].values()}
            for path, info in local_tree["files"].items():
                 h = info["partial_hash"]
                 if h not in local_hashes: local_hashes[h] = []
                 local_hashes[h].append(path)
                 
            cloud_hashes = {}
            for path, info in cloud_tree["files"].items():
                h = info.get("partial_hash")
                if h:
                    if h not in cloud_hashes: cloud_hashes[h] = []
                    cloud_hashes[h].append(path)
                    
            for new_path in paths_to_add:
                new_info = local_tree["files"][new_path]
                new_hash = new_info["partial_hash"]
                if new_hash in cloud_hashes:
                    for old_path in cloud_hashes[new_hash]:
                        if old_path in paths_to_delete_later:
                            old_info = cloud_tree["files"][old_path]
                            if old_info["size"] == new_info["size"]:
                                new_name = Path(new_path).name
                                old_parent = str(Path(old_path).parent)
                                new_parent = str(Path(new_path).parent)
                                if old_parent == new_parent:
                                    if is_dry_run:
                                         self.log_ui(f"{tr('simu_rename', '[SIMU] Renommage:')} {old_path} -> {new_path}", "yellow")
                                         paths_to_upload_later.remove(new_path)
                                         paths_to_delete_later.remove(old_path)
                                         info = cloud_tree["files"].pop(old_path)
                                         cloud_tree["files"][new_path] = info
                                    else:
                                         renamed_in_place.append((old_path, new_path, old_info['id'], new_name))
                                         paths_to_upload_later.remove(new_path)
                                         paths_to_delete_later.remove(old_path)
                                         info = cloud_tree["files"].pop(old_path)
                                         info['mtime'] = new_info['mtime']
                                         info['partial_hash'] = new_info['partial_hash']
                                         cloud_tree["files"][new_path] = info
                                    break 

                             
            for old_p, new_p, eid, name in renamed_in_place:
                if self.app.is_mobile: time.sleep(0.002)
                if self.stop_event.is_set(): break
                while self.is_paused: time.sleep(0.5)
                if not self.rename_remote_entry(eid, name, api_key):
                    self.log_ui(f"{tr('failure_rename', 'Échec renommage')} {new_p}", "red")
                    paths_to_upload_later.add(new_p)
                    paths_to_delete_later.add(old_p)
                else:
                    if str(Path(old_p).parent) == str(Path(new_p).parent):
                         files_renamed_count += 1
                         self.log_ui(f"{tr('log_renamed', 'Renommé:')} {old_p} -> {new_p}", "yellow")
                    else:
                         files_moved_count += 1
                         self.log_ui(f"{tr('log_moved', 'Déplacé:')} {old_p} -> {new_p}", "yellow")

                               
            files_to_delete_ids = []
            for p in paths_to_delete_later:
                if p in cloud_tree["files"]:
                    folders_to_delete_ids.append(cloud_tree["files"][p]["id"])
                    del cloud_tree["files"][p]
                    if is_dry_run: self.log_ui(f"{tr('simu_delete_file', '[SIMU] Suppression fichier:')} {p}", "red")
                    else: self.log_ui(f"{tr('debug_delete_file', '[DEBUG] Suppr:')} {p}")

                                   
            for p in paths_to_check:
                l_info = local_tree["files"][p]
                c_info = cloud_tree["files"][p]
                if l_info['size'] != c_info.get('size') or l_info['partial_hash'] != c_info.get('partial_hash'):
                    self.log_ui(f"{tr('log_modified', 'Modifié:')} {p}", "yellow")
                    files_to_upload.append(p)
            for p in paths_to_upload_later: files_to_upload.append(p)

                               
            if is_dry_run:
                for p in files_to_upload: self.log_ui(f"{tr('log_simu_upload', '[SIMU] Upload:')} {p}")
                self.log_ui(tr("log_end_simu", "--- FIN SIMULATION ---"), "yellow")
                return

            total = len(files_to_upload)
            save_interval = 5
            if total > 10000: save_interval = 1000
            elif total > 2000: save_interval = 200
            elif total > 200: save_interval = 50
            
            self.log_ui(f"{tr('log_files_to_upload', 'Fichiers à uploader:')} {total} (Sauvegarde état tous les {save_interval})")
            self.total_size = 0
            self.total_transferred = 0
            for p in files_to_upload:
                self.total_size += local_tree["files"][p]["size"]
                
            self.update_status_ui(f"{tr('status_modifications', 'Modifications:')} {total} fichier(s)", COL_VIOLET)
            
            upload_queue = Queue()
            result_queue = Queue()
            for p in files_to_upload:
                upload_queue.put((p, local_tree["files"][p]))
                
            workers = []
            for i in range(nb_workers):
                t = threading.Thread(
                    target=self.upload_worker, 
                    args=(upload_queue, result_queue, api_key, workspace_id), 
                    daemon=True, 
                    name=f"Worker-{i+1}"
                )
                t.start()
                workers.append(t)
                
            processed = 0
            while processed < total:
                if self.stop_event.is_set(): break
                              
                rel_path, res = result_queue.get()
                processed += 1
                
                if res:
                    cloud_tree["files"][rel_path] = res
                    files_success_count += 1
                    total_bytes_uploaded += res.get("size", 0)
                    self.log_ui(f"Succès: {rel_path}")
                    if processed % save_interval == 0: self.save_local_cloud_tree(cloud_tree, app_data_state_dir)
                else:
                    files_failed_count += 1
                    self.log_ui(f"Échec: {rel_path}", "red")

            all_del_ids = folders_to_delete_ids + files_to_delete_ids
            files_deleted_count = len(all_del_ids)
            
            if all_del_ids and not self.stop_event.is_set():
                while self.is_paused: time.sleep(0.5)
                self.log_ui(f"Suppression de {len(all_del_ids)} éléments...", "red")
                self.app.api_client.delete_entries(entry_ids=all_del_ids, delete_forever=True)

            if not self.stop_event.is_set():
                self.save_local_cloud_tree(cloud_tree, app_data_state_dir)
                
                                       
                tree_full = os.path.join(app_data_state_dir, CLOUD_TREE_FILE)
                if os.path.exists(tree_full):
                    st_tree = os.stat(tree_full)
                    ph_tree = self.get_partial_hash(tree_full, st_tree.st_size)
                    tree_rel_path = f"{SYNC_STATE_FOLDER}/{CLOUD_TREE_FILE}"
                    tree_info = {"full_path": tree_full, "size": st_tree.st_size, "mtime": st_tree.st_mtime, "partial_hash": ph_tree}
                    res_tree = None
                    for _ in range(PART_UPLOAD_RETRIES):
                         res_tree = self.upload_file_router(tree_info, tree_rel_path, api_key, workspace_id, "System")
                         if res_tree: break
                         time.sleep(2)
                    if res_tree:
                         self.log_ui(tr("log_state_saved", "État sauvegardé sur le cloud."), "green")

            if self.stop_event.is_set():
                self.log_ui("--- ANNULÉ ---", "red")
                self.update_status_ui("Annulé.", COL_ROUGE)
            else:
                self.log_ui("--- TERMINÉ ---", "green")
                self.update_status_ui("Terminé.", COL_VERT)
                end_time = time.time()
                total_time = max(1, end_time - start_time)
                                                                               
                
                stats = {
                    'success': files_success_count,
                    'renamed': files_renamed_count + files_moved_count,
                    'deleted': files_deleted_count,
                    'failed': files_failed_count,
                    'bytes': total_bytes_uploaded
                }
                report = self.generate_report(stats, total_time, "TERMINÉ")
                self.log_ui(f"\n--- BILAN ---\n{report}")
                
                async def show_report():
                    await self.app.main_window.dialog(toga.InfoDialog("Rapport", report))
                asyncio.run_coroutine_threadsafe(show_report(), self.app.loop)
                
        except Exception as e:
            self.log_ui(f"{tr('log_fatal_error', 'ERREUR FATALE:')} {e}", "red")
            import traceback
            traceback.print_exc()
        finally:
            def _reset(): self._set_ui_running(False)
            self.app.loop.call_soon_threadsafe(_reset)