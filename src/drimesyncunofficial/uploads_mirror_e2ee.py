import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
import asyncio
import json
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
from drimesyncunofficial.constants import (
    COL_GRIS, COL_TEXT_GRIS, COL_VERT, COL_ROUGE, COL_JAUNE, COL_BLEU, COL_VIOLET, COL_BLEU2, 
    API_BASE_URL, HTTP_TIMEOUT, MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK, 
    E2EE_CRYPTO_ALGO, SYNC_STATE_FOLDER_NAME, CLOUD_TREE_FILE_NAME, EXCLUDE_FILE_NAME, 
    PARTIAL_HASH_CHUNK_SIZE, CHUNK_SIZE,
    CONF_KEY_API_KEY, CONF_KEY_WORKERS, CONF_KEY_SEMAPHORES, CONF_KEY_USE_EXCLUSIONS,
    CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD, ANDROID_DOWNLOAD_PATH
)
from drimesyncunofficial.api_client import DrimeClientError
from drimesyncunofficial.utils import (
    format_size, get_salt_path, derive_key, generate_or_load_salt,
    E2EE_encrypt_file, E2EE_decrypt_file, E2EE_encrypt_name, 
    get_remote_path_for_tree_file, load_exclusion_patterns, 
    E2EE_encrypt_bytes, E2EE_decrypt_bytes, truncate_path_smart,
    sanitize_filename_for_upload, E2EE_decrypt_name
)
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background

SYNC_STATE_FOLDER = SYNC_STATE_FOLDER_NAME
CLOUD_TREE_FILE = CLOUD_TREE_FILE_NAME

BATCH_SIZE = 10
PART_UPLOAD_RETRIES = 10
MULTIPART_THRESHOLD = 30 * 1024 * 1024

simple_upload_limiter: Optional[threading.Semaphore] = None
class MirrorUploadE2EEManager(LoggerMixin):
    """
    Gestionnaire de Synchronisation Miroir avec Chiffrement E2EE.
    Synchronise un dossier local vers un workspace distant en chiffrant tout à la volée.
    - Supporte les modes Standard, Advanced et ZK.
    - Gère l'état de synchronisation chiffré localement et sur le cloud.
    - Assure la confidentialité totale des données (noms et contenus).
    """
    def __init__(self, app: Any):
        self.app: Any = app
        self.mirror_local_path: str = self.app.config_data.get('folder_e2ee_path', '')
        self.window: Optional[toga.Window] = None
        self.lbl_warning_ws: Optional[toga.Label] = None
        self.lbl_conflict_warning: Optional[toga.Label] = None
        self.lbl_progress: Optional[toga.Label] = None
        self.log_output: Optional[toga.MultilineTextInput] = None 
        self.txt_logs: Optional[toga.MultilineTextInput] = None
        self.btn_sync: Optional[toga.Button] = None
        self.btn_simu: Optional[toga.Button] = None
        self.btn_force: Optional[toga.Button] = None
        self.btn_pause: Optional[toga.Button] = None
        self.btn_cancel: Optional[toga.Button] = None
        self.box_controls: Optional[toga.Box] = None
        self.box_secondary_btns: Optional[toga.Box] = None
        self.box_actions_container: Optional[toga.Box] = None
        self.selection_mirror_ws: Optional[toga.Selection] = None
        self.e2ee_mode: str = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
        self.e2ee_password: str = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
        self.e2ee_key: Optional[bytes] = None 
        self.is_running: bool = False
        self.is_paused: bool = False
        self.stop_event: threading.Event = threading.Event()
        self.simple_upload_limiter: Optional[threading.Semaphore] = None
        self.total_size: int = 0
        self.total_transferred: int = 0
        self.progress_lock: threading.Lock = threading.Lock()
        self.main_box_content = None
    async def _show_error_dialog_async(self, title: str, message: str) -> None:
        await self.app.main_window.dialog(toga.ErrorDialog(title, message))



    def show(self) -> None:
        """Affiche l'interface de configuration du miroir E2EE."""
        try:
            self.app.config_data = self.app.charger_config()
            self.e2ee_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
            self.e2ee_password = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
            if self.e2ee_mode == MODE_NO_ENC: self.e2ee_mode = MODE_E2EE_STANDARD
        except: pass
        if not self.e2ee_password:
             asyncio.ensure_future(self._show_error_dialog_async("Configuration Requise", "Mot de passe E2EE manquant."))
             return
        try:
             salt = generate_or_load_salt(self.app.paths)
             if not salt:
                 asyncio.ensure_future(self._show_error_dialog_async("Erreur Sel", "Impossible de charger le sel."))
                 return
             self.e2ee_key = derive_key(str(self.e2ee_password), salt)
        except Exception as e:
             asyncio.ensure_future(self._show_error_dialog_async("Erreur Clé", f"Détail: {e}"))
             return
        mode_detail_label = {
            MODE_E2EE_STANDARD: f"E2EE - Standard ({E2EE_CRYPTO_ALGO})",
            MODE_E2EE_ADVANCED: f"E2EE - Avancé ({E2EE_CRYPTO_ALGO})",
            MODE_E2EE_ZK: f"E2EE - Zero Knowledge ({E2EE_CRYPTO_ALGO})",
        }.get(self.e2ee_mode, "MODE INCONNU")
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))
        box.add(create_back_button(self.go_back))
        box.add(toga.Label(f"--- MODE CHIFFRÉ ---", style=Pack(font_weight=BOLD, color=COL_ROUGE, margin_bottom=5, font_size=12)))
        box.add(toga.Label(mode_detail_label, style=Pack(font_size=10, margin_bottom=20, color=COL_TEXT_GRIS)))
        box.add(toga.Label("Source (Dossier Local) :", style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.lbl_mirror_path = toga.Label(self.mirror_local_path or "Aucun dossier choisi", style=Pack(margin_bottom=5, color='gray', flex=1))
        box.add(self.lbl_mirror_path)
        box.add(toga.Button("📂 Choisir le dossier...", on_press=self.action_mirror_choose_folder, style=Pack(margin_bottom=20, flex=1)))
        box.add(toga.Label("Destination (Workspace) :", style=Pack(font_weight=BOLD, margin_bottom=5)))
        items = ["Espace Personnel (ID: 0)"]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: items.append(f"{ws['name']} (ID: {ws['id']})")
        self.selection_mirror_ws = toga.Selection(items=items, on_change=self.update_warnings, style=Pack(width=220, margin_bottom=10))
        current_saved_ws_id = self.app.config_data.get('workspace_e2ee_id', '0')
        selected_item_str = next((item for item in items if f"(ID: {current_saved_ws_id})" in item), items[0])
        self.selection_mirror_ws.value = selected_item_str
        box.add(self.selection_mirror_ws)
        self.lbl_warning_ws = toga.Label("⚠️ Déconseillé dans l'Espace Personnel.\nCréez un workspace dédié.", style=Pack(font_size=8, color=COL_ROUGE, font_weight=BOLD, margin_bottom=10, visibility='hidden', flex=1))
        box.add(self.lbl_warning_ws)
        self.lbl_conflict_warning = toga.Label("⚠️ CONFLIT : Workspace utilisé par le\nmiroir STANDARD. Risque de désynchronisation.", style=Pack(font_size=8, color=COL_JAUNE, font_weight=BOLD, margin_bottom=20, visibility='hidden', flex=1))
        box.add(self.lbl_conflict_warning)
        self.btn_sync = toga.Button("🟩 SYNCHRONISER (E2EE)", on_press=self.action_mirror_sync_wrapper, style=Pack(height=50, background_color=COL_VERT, color='white', font_weight=BOLD, flex=1))
        box.add(self.btn_sync)
        self.box_secondary_btns = toga.Box(style=Pack(direction=ROW, margin_top=5))
        self.btn_simu = toga.Button("Simulation", on_press=self.action_mirror_simu_wrapper, style=Pack(flex=1, margin_right=5, height=40, background_color=COL_JAUNE, color='white'))
        self.btn_force = toga.Button("Synchro Forcée", on_press=self.action_mirror_force_wrapper, style=Pack(flex=1, margin_left=5, height=40, background_color=COL_GRIS, color=COL_ROUGE, font_weight=BOLD))
        self.box_secondary_btns.add(self.btn_simu)
        self.box_secondary_btns.add(self.btn_force)
        box.add(self.box_secondary_btns)
        self.box_controls = toga.Box(style=Pack(direction=ROW, visibility='hidden', height=0, flex=1))
        self.btn_pause = toga.Button("⏸️ Pause", on_press=self.action_toggle_pause, style=Pack(flex=1, margin_right=5, height=50, background_color=COL_JAUNE, color='white', visibility='hidden'))
        self.btn_cancel = toga.Button("⏹️ Annuler Tout", on_press=self.action_cancel, style=Pack(flex=1, margin_left=5, height=50, background_color=COL_ROUGE, color='white', font_weight=BOLD, visibility='hidden'))
        self.box_controls.add(self.btn_pause)
        self.box_controls.add(self.btn_cancel)
        box.add(self.box_controls)

        self.lbl_progress = toga.Label("", style=Pack(font_weight=BOLD, margin_bottom=5, font_size=10, color=COL_JAUNE, flex=1))
        box.add(self.lbl_progress)
        box.add(toga.Label("Log :", style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.txt_logs = create_logs_box(height=150, margin=5)
        self.log_output = self.txt_logs 
        box.add(self.txt_logs)
        self.update_warnings(None)  
        self._set_ui_running(False)
        main_container.content = box
        self.main_box_content = main_container 
        self.app.changer_ecran(main_container)
    def _set_ui_running(self, running: bool) -> None:
        """Bascule l'interface entre mode Configuration et mode Exécution."""
        self.is_running = running
        def _update():
            if running:
                self.btn_sync.style.visibility = 'hidden'; self.btn_sync.style.height = 0; self.btn_sync.style.width = 0; self.btn_sync.style.margin_bottom = 0
                self.box_secondary_btns.style.visibility = 'hidden'; self.box_secondary_btns.style.height = 0; self.box_secondary_btns.style.width = 0; self.box_secondary_btns.style.margin_bottom = 0
                
                self.box_controls.style.visibility = 'visible'; self.box_controls.style.height = 50
                try: del self.box_controls.style.width 
                except: pass
                
                self.btn_pause.style.visibility = 'visible'; self.btn_pause.style.height = 50
                try: del self.btn_pause.style.width; del self.btn_pause.style.flex; self.btn_pause.style.flex = 1
                except: pass
                self.btn_pause.style.margin_right = 5
                
                self.btn_cancel.style.visibility = 'visible'; self.btn_cancel.style.height = 50
                try: del self.btn_cancel.style.width; del self.btn_cancel.style.flex; self.btn_cancel.style.flex = 1
                except: pass
                self.btn_cancel.style.margin_left = 5
                
                self.is_paused = False; self.btn_pause.enabled = True; self.btn_cancel.enabled = True
                self.btn_pause.text = "⏸️ Pause"; self.btn_pause.style.background_color = COL_JAUNE
                self.latest_log = "Préparation..."
            else:
                self.box_controls.style.visibility = 'hidden'; self.box_controls.style.height = 0; self.box_controls.style.width = 0
                self.btn_pause.style.visibility = 'hidden'; self.btn_pause.style.height = 0; self.btn_pause.style.width = 0
                self.btn_cancel.style.visibility = 'hidden'; self.btn_cancel.style.height = 0; self.btn_cancel.style.width = 0
                
                self.btn_sync.style.visibility = 'visible'; self.btn_sync.style.height = 50; self.btn_sync.style.margin_bottom = 5
                try: del self.btn_sync.style.width
                except: pass
                
                self.box_secondary_btns.style.visibility = 'visible'; self.box_secondary_btns.style.height = 40; self.box_secondary_btns.style.margin_bottom = 5
                try: del self.box_secondary_btns.style.width
                except: pass
                
                self.btn_simu.enabled = True; self.btn_sync.enabled = True; self.btn_force.enabled = True
                if self.lbl_progress:
                    self.lbl_progress.text = "Terminé."
                    self.lbl_progress.style.color = COL_VERT
            self.app.main_window.content.refresh()
        self.app.loop.call_soon_threadsafe(_update)

    def update_status_ui(self, text: str, color: Optional[str] = None) -> None:
        self.last_text = text
        style = {'color': color} if color else None
        safe_update_label(self.app, self.lbl_progress, text, style)

    def _spinner_loop(self):
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        idx = 0
        while self.is_running and not self.stop_event.is_set():
            if not self.is_paused:
                txt = getattr(self, 'last_text', '')
                if txt and "Terminé" not in txt:
                    char = chars[idx % len(chars)]
                    idx += 1
                    safe_update_label(self.app, self.lbl_progress, f"{txt}   {char}")
            time.sleep(0.1)
    def update_warnings(self, widget: Any) -> None:
        if not self.lbl_warning_ws: return
        sel = self._get_selected_workspace_id()
        std_id = self.app.config_data.get('workspace_standard_id', '0')
        if sel == '0': self.lbl_warning_ws.style.visibility = 'visible'
        else: self.lbl_warning_ws.style.visibility = 'hidden'
        if sel == std_id: self.lbl_conflict_warning.style.visibility = 'visible'
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
        """Déclenche la sélection de dossier. Sur Android, utilise le navigateur maison."""
        if self.app.is_mobile:
            def on_folder_picked(result_path):
                self.app.main_window.content = self.main_box_content
                if result_path:
                    self.mirror_local_path = str(result_path)
                    self.lbl_mirror_path.text = self.mirror_local_path
                    self.app.config_data['folder_e2ee_path'] = self.mirror_local_path
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
                self.app.config_data['folder_e2ee_path'] = self.mirror_local_path
                self._save_config_file()
        asyncio.ensure_future(_ask())
    def _save_config_file(self) -> None:
        self.app.config_data['workspace_e2ee_id'] = self._get_selected_workspace_id()
        config_to_save = self.app.config_data.copy()
        is_desktop = toga.platform.current_platform not in {'android', 'iOS', 'web'}
        if is_desktop:
            config_to_save['api_key'] = ""
            config_to_save['e2ee_password'] = ""
        try:
            with open(self.app.config_path, 'w', encoding='utf-8') as f: 
                json.dump(config_to_save, f, indent=4)
        except: pass
    def action_toggle_pause(self, widget: Any) -> None:
        if not self.is_running: return
        if self.is_paused:
            self.is_paused = False
            self.btn_pause.text = "⏸️ Pause"
            self.btn_pause.style.background_color = COL_JAUNE
            self.log_ui("Reprise des opérations...")
            self.update_status_ui("Reprise...", COL_JAUNE)
        else:
            self.is_paused = True
            self.btn_pause.text = "▶️ Reprendre"
            self.btn_pause.style.background_color = COL_VERT
            self.log_ui("PAUSE DEMANDÉE...", "yellow")
            self.update_status_ui("EN PAUSE", COL_JAUNE)
    async def action_cancel(self, widget: Any) -> None:
        if not self.is_running: return
        if await self.app.main_window.dialog(toga.QuestionDialog("Confirmation", "Voulez-vous vraiment annuler la synchronisation ?")):
            self.log_ui("ANNULATION EN COURS...", "red")
            self.update_status_ui("Annulation en cours...", COL_ROUGE)
            self.stop_event.set()
    async def action_mirror_simu_wrapper(self, widget: Any) -> None:
        await self.launch_sync_thread(is_dry_run=True)
    async def action_mirror_sync_wrapper(self, widget: Any) -> None:
        await self.launch_sync_thread(is_dry_run=False)
    async def action_mirror_force_wrapper(self, widget: Any) -> None:
        if await self.app.main_window.dialog(toga.QuestionDialog("DANGER", "Cette action va EFFACER tout le contenu du Workspace distant (fichiers chiffrés inclus) et tout ré-uploader.\n\nContinuer ?")):
            await self.launch_sync_thread(is_dry_run=False, force_sync=True)
    async def launch_sync_thread(self, is_dry_run: bool, force_sync: bool = False) -> None:
        """Lance le thread principal de synchronisation."""
        if self.is_running: return
        if not self.mirror_local_path or not os.path.exists(self.mirror_local_path):
             await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Dossier local manquant."))
             return
        self._save_config_file()
        self.stop_event.clear()
        self.txt_logs.value = ""
        self.lbl_progress.text = ""
        self._set_ui_running(True)
        self.last_text = "Préparation..."
        self.last_text = "Préparation..."
        run_in_background(self._spinner_loop)
        t = run_in_background(
            self._thread_mirror_logic,
            self.mirror_local_path, 
            self._get_selected_workspace_id(), 
            is_dry_run, 
            force_sync
        )
        t.name = "Thread-MirrorE2EE-Logic"
    def _get_local_state_dir(self, workspace_id: str) -> str:
        ws_name = "Workspace"
        if workspace_id == "0": ws_name = "Espace_Personnel"
        else:
            for w in self.app.workspace_list_cache:
                if str(w.get('id')) == str(workspace_id): ws_name = w.get('name', 'Inconnu'); break
        safe_name = "".join([c for c in ws_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        folder_name = f"{safe_name}_{workspace_id}_E2EE" 
        state_dir = self.app.paths.data / "MirrorStates" / folder_name
        if not state_dir.exists(): state_dir.mkdir(parents=True, exist_ok=True)
        return str(state_dir)
    def _calculate_remote_path(self, rel_path: str, is_folder: bool = False) -> str:
        """
        Calcule le chemin distant chiffré selon le mode E2EE.
        - ZK : Tout chiffré + .enc
        - Advanced : Noms chiffrés, extensions claires.
        """
        parts = rel_path.replace("\\", "/").split("/")
        processed_parts = []
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            should_encrypt = False
            if self.e2ee_mode == MODE_E2EE_ZK: should_encrypt = True
            elif self.e2ee_mode == MODE_E2EE_ADVANCED:
                if is_last and not is_folder: should_encrypt = True
            if should_encrypt:
                if is_last and not is_folder:
                    base, ext = os.path.splitext(part)
                    enc_base = E2EE_encrypt_name(base, self.e2ee_key)
                    if self.e2ee_mode == MODE_E2EE_ZK:
                        enc_full_name = E2EE_encrypt_name(part, self.e2ee_key)
                        processed_parts.append(f"{enc_full_name}.enc")
                    else: 
                        processed_parts.append(f"{enc_base}{ext}")
                else:
                    processed_parts.append(E2EE_encrypt_name(part, self.e2ee_key))
            else:
                if is_last and not is_folder:
                    processed_parts.append(f"{part}.enc")
                else:
                    if part == "0": processed_parts.append("0.renamed")
                    else: processed_parts.append(part)
        return "/".join(processed_parts)
    def delete_all_cloud_content(self, api_key: str, workspace_id: str) -> bool:
        """Supprime tout le contenu distant (pour la synchro forcée) avec pagination."""
        self.log_ui("[red]MODE FORCE-SYNC : NETTOYAGE COMPLET...[/red]")
        params = {}
        if workspace_id != "0": params['workspaceId'] = workspace_id
        
        total_deleted = 0
        while True:
            try:
                if self.stop_event.is_set(): return False
                self.log_ui(f"Récupération de la liste des fichiers...")
                try:
                    data = self.app.api_client.list_files(params=params)
                except Exception as e:
                    self.log_ui(f"Erreur listing: {e}", "red")
                    return False
            except Exception as e:
                self.log_ui(f"Exception boucle loop: {e}", "red")
                return False
                
            if not data or 'data' not in data: break
            items = data['data']
            if not items: break
            
            ids_to_delete = [str(item['id']) for item in items]
            if not ids_to_delete: break
            
            count = len(ids_to_delete)
            self.log_ui(f"  > Lot de {count} élément(s) à supprimer...")
            
            batch_size = 50
            timeout_val = None 
            
            if self.app.is_mobile:
                 batch_size = 20
                 timeout_val = 60

            for i in range(0, count, batch_size):
                if self.stop_event.is_set(): return False
                batch = ids_to_delete[i:i+batch_size]
                try:
                    kwargs = {}
                    if timeout_val: kwargs['timeout'] = timeout_val
                    self.app.api_client.delete_entries(entry_ids=batch, delete_forever=True, **kwargs)
                    total_deleted += len(batch)
                    self.log_ui(f"    - Supprimés : {len(batch)} (Total: {total_deleted})")
                except Exception as e:
                    self.log_ui(f"    - Erreur suppression lot: {e}", "red")

        self.log_ui(f"[green]Cloud vidé ({total_deleted} éléments supprimés).[/green]")
        return True
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
        except: return None
    def get_local_tree(self, root_folder: str, app_data_state_dir: str, use_exclusions: bool = True) -> Dict[str, Any]:
        """Scanne le dossier local pour construire l'arbre de fichiers."""
        self.log_ui(f"Scan du dossier local : {root_folder}")
        tree = {"folders": set(), "files": {}}
        exclusions = load_exclusion_patterns(self.app.paths, use_exclusions)
        root_path_obj = Path(root_folder)
        for root, dirs, files in os.walk(root_folder):
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
                        if ph: tree["files"][rel] = {"full_path": str(full), "size": st.st_size, "mtime": st.st_mtime, "partial_hash": ph}
                except: pass
        return tree
    def load_local_cloud_tree(self, app_data_state_dir: str, api_key: str, ws_id: str) -> Dict[str, Any]:
        """Charge l'état distant connu (depuis le disque local ou le cloud si absent)."""
        path = os.path.join(app_data_state_dir, CLOUD_TREE_FILE)
        if not os.path.exists(path):
            self.log_ui(f"[DEBUG] État local manquant. Recherche Recovery...")
            target_filename_clear = CLOUD_TREE_FILE
            p_cloud_tree = Path(CLOUD_TREE_FILE)
            base, ext = p_cloud_tree.stem, p_cloud_tree.suffix
            if self.e2ee_mode == MODE_E2EE_ADVANCED:
                enc_base = E2EE_encrypt_name(base, self.e2ee_key)
                target_filename_enc = f"{enc_base}{ext}"
            elif self.e2ee_mode == MODE_E2EE_ZK:
                target_filename_enc = E2EE_encrypt_name(CLOUD_TREE_FILE, self.e2ee_key) + ".enc"
            else:
                target_filename_enc = E2EE_encrypt_name(CLOUD_TREE_FILE, self.e2ee_key)
            candidates = [target_filename_clear]
            if target_filename_enc != target_filename_clear:
                candidates.append(target_filename_enc)
            found_file = None
            for name in candidates:
                 data = self.app.api_client.list_files(params={"query": name, "workspaceId": ws_id})
                 if data and 'data' in data:
                     for f in data['data']:
                         if f['name'] == name:
                             found_file = f; break
                 if found_file: break
            if found_file:
                self.log_ui(f"[INFO] Fichier d'état trouvé (ID: {found_file['id']}). Récupération...")
                try:
                    dl_url = f"{API_BASE_URL}/file-entries/download/{found_file['hash']}"
                    with self.app.api_client.get_download_stream(dl_url) as r:
                        if r.status_code == 200:
                            content = r.content
                            try:
                                json.loads(content)
                                with open(path, 'wb') as f: f.write(content)
                                self.log_ui("[SUCCESS] État restauré (Clair).", "green")
                            except:
                                decrypted = E2EE_decrypt_file(content, self.e2ee_key)
                                if decrypted:
                                    with open(path, 'wb') as f: f.write(decrypted)
                                    self.log_ui("[SUCCESS] État restauré et déchiffré.", "green")
                                else:
                                    self.log_ui("[ERROR] Fichier trouvé mais impossible de le lire/déchiffrer.", "red")
                except Exception as e:
                    self.log_ui(f"[ERROR] Recovery failed: {e}", "red")
            else:
                self.log_ui("[INFO] Pas d'état distant. Départ à zéro.", "yellow")
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f: content = f.read()
                try:
                    return json.loads(content)
                except:
                    if self.e2ee_key:
                        decrypted = E2EE_decrypt_bytes(content, self.e2ee_key)
                        if decrypted: return json.loads(decrypted)
            except: pass
        return {"folders": {}, "files": {}}
    def save_local_cloud_tree(self, tree: Dict[str, Any], app_data_state_dir: str, encrypt: bool = False) -> None:
        """Sauvegarde l'état distant connu sur le disque local (chiffré si demandé)."""
        path = Path(app_data_state_dir) / CLOUD_TREE_FILE
        try:
            data_bytes = json.dumps(tree, indent=2).encode('utf-8')
            if encrypt and self.e2ee_key:
                encrypted_data = E2EE_encrypt_bytes(data_bytes, self.e2ee_key)
                with open(path, 'wb') as f: f.write(encrypted_data)
            else:
                with open(path, 'wb') as f: f.write(data_bytes)
        except: pass
    def handle_folder_creation(self, rel_folder_path: str, cloud_tree: Dict[str, Any], ws_id: str, is_dry_run: bool) -> None:
        """Crée récursivement les dossiers manquants sur le cloud (noms chiffrés)."""
        cloud_path_enc = self._calculate_remote_path(rel_folder_path, is_folder=True)
        if rel_folder_path in cloud_tree["folders"]: return
        if "/" in rel_folder_path:
            parent_rel = rel_folder_path.rsplit('/', 1)[0]
            if parent_rel not in cloud_tree["folders"]:
                self.handle_folder_creation(parent_rel, cloud_tree, ws_id, is_dry_run)
            parent_id = cloud_tree["folders"][parent_rel]["id"]
        else: parent_id = ws_id
        if is_dry_run:
            self.log_ui(f"[SIMU] Création dossier: {rel_folder_path} -> {cloud_path_enc}")
            cloud_tree["folders"][rel_folder_path] = {"id": f"SIMU_ID_{rel_folder_path}", "name": cloud_path_enc.split("/")[-1]}
            return
        folder_name_to_create = cloud_path_enc.split("/")[-1]
        try:
            entry = self.app.api_client.create_folder(name=folder_name_to_create, parent_id=parent_id if parent_id != ws_id else None, workspace_id=ws_id)
            if entry and (entry.get('folder') or entry).get('id'):
                cloud_tree["folders"][rel_folder_path] = entry.get('folder') or entry
                self.log_ui(f"Dossier créé: {rel_folder_path}")
        except DrimeClientError:
                                                       
             data = self.app.api_client.list_files(params={"folderId": parent_id if parent_id != ws_id else None, "workspaceId": ws_id})
             if data and 'data' in data:
                 for i in data['data']:
                     if i['type'] == 'folder' and i['name'] == folder_name_to_create:
                         cloud_tree["folders"][rel_folder_path] = i
                         return
    def rename_remote_entry(self, entry_id: str, new_name: str, api_key: str) -> Optional[str]:
        try:
            resp = self.app.api_client.rename_entry(entry_id, new_name)
            if resp.status_code == 200:
                data = resp.json()
                return (data.get('id') or data.get('fileEntry', {}).get('id'))
        except: pass
        return None
    def upload_worker(self, q: Queue, res_q: Queue, api_key: str, ws_id: str) -> None:
        """Worker thread pour l'upload E2EE."""
        thread_name = threading.current_thread().name
        while True:
            try: item = q.get_nowait()
            except: break
            if self.stop_event.is_set(): 
                q.task_done(); continue
            while self.is_paused: time.sleep(0.5)
            rel_path, info = item
            remote_path = self._calculate_remote_path(rel_path, is_folder=False)
            self.log_ui(f"[DEBUG] [{thread_name}] Start: {rel_path}")
            result = None
            try:
                result = self.upload_file_router_e2ee(info, remote_path, api_key, ws_id, thread_name)
            except Exception as e:
                self.log_ui(f"[{thread_name}] CRASH Worker: {e}", "red")
            res_q.put((rel_path, result))
            q.task_done()
    def parse_api_response_for_id(self, response: Any) -> Optional[Dict[str, Any]]:
        if not response: return None
        if isinstance(response, dict) and 'error_code' in response: return None
        if 'fileEntry' in response: return response['fileEntry']
        elif 'id' in response and 'name' in response: return response
        return None
    def upload_file_router_e2ee(self, local_info: Dict[str, Any], cloud_relative_path: str, api_key: str, workspace_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        file_size = local_info["size"]
        try:
            if file_size > MULTIPART_THRESHOLD:
                return self.upload_multipart_e2ee(local_info, cloud_relative_path, api_key, workspace_id, thread_name)
            else:
                with self.simple_upload_limiter:
                    return self.upload_simple_e2ee(local_info, cloud_relative_path, api_key, workspace_id, thread_name)
        except Exception as e:  
            self.log_ui(f"[DEBUG] [{thread_name}] Exception routeur: {e}")
            return None
    def upload_simple_e2ee(self, local_info: Dict[str, Any], remote_path: str, api_key: str, ws_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        """
        Upload simple E2EE.
        1. Chiffre le fichier vers un fichier temporaire.
        2. Upload le fichier temporaire.
        3. Supprime le fichier temporaire.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
                encrypted_bytes = E2EE_encrypt_file(local_info["full_path"], self.e2ee_key)
                tmp_file.write(encrypted_bytes)
            enc_filename = Path(remote_path).name
            resp = self.app.api_client.upload_simple(tmp_path, ws_id, remote_path, custom_file_name=enc_filename)
            if tmp_path: Path(tmp_path).unlink(missing_ok=True)
            if resp.status_code in [200, 201]:
                fe = resp.json().get('fileEntry')
                if fe:
                    with self.progress_lock:
                        self.total_transferred += local_info["size"]
                        percent = int((self.total_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                        self.update_status_ui(f"Upload {format_size(self.total_transferred)}/{format_size(self.total_size)} {percent}%", COL_BLEU2)
                    return {"id": fe["id"], "size": local_info["size"], "mtime": local_info["mtime"], "partial_hash": local_info["partial_hash"]}
            return None
        except Exception as e:
            self.log_ui(f"[{thread_name}] Err Simple: {e}", "red")
            if tmp_path: Path(tmp_path).unlink(missing_ok=True)
            return None
    def upload_multipart_e2ee(self, local_info: Dict[str, Any], remote_path: str, api_key: str, ws_id: str, thread_name: str) -> Optional[Dict[str, Any]]:
        """
        Upload multipart E2EE.
        Similaire à l'upload simple, mais gère le découpage en chunks pour les gros fichiers.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
                encrypted_bytes = E2EE_encrypt_file(local_info["full_path"], self.e2ee_key)
                tmp_file.write(encrypted_bytes)
            enc_size = Path(tmp_path).stat().st_size
            num_parts = math.ceil(enc_size / CHUNK_SIZE)
            file_name = Path(remote_path).name
            init_resp = self.app.api_client.upload_multipart_init(file_name, enc_size, remote_path, ws_id)
            if init_resp.status_code not in [200, 201]: 
                if tmp_path: Path(tmp_path).unlink(missing_ok=True)
                return None
            upload_id = init_resp.json()['uploadId']
            key = init_resp.json()['key']
            uploaded_parts = []
            with open(tmp_path, "rb") as f:
                part_number = 1
                while part_number <= num_parts:
                    if self.stop_event.is_set(): raise Exception("Cancelled")
                    while self.is_paused: time.sleep(0.5)

                    if self.app.is_mobile: time.sleep(0.005)

                    batch_end = min(part_number + BATCH_SIZE - 1, num_parts)
                    batch_nums = list(range(part_number, batch_end + 1))
                    sign_resp = self.app.api_client.upload_multipart_sign_batch(key, upload_id, batch_nums)
                    if sign_resp.status_code not in [200, 201]:
                        if tmp_path: Path(tmp_path).unlink(missing_ok=True)
                        return None
                    urls_map = {u['partNumber']: u['url'] for u in sign_resp.json()['urls']}
                    for pn in batch_nums:
                        if self.app.is_mobile: time.sleep(0.005)
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk: break
                        r = self.app.api_client.upload_multipart_put_chunk(urls_map[pn], chunk)
                        if r.status_code in [200, 201]:
                            uploaded_parts.append({"PartNumber": pn, "ETag": r.headers.get("ETag", "").strip('"')})
                            with self.progress_lock:
                                self.total_transferred += len(chunk)
                                percent = int((self.total_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                                self.update_status_ui(f"Upload {format_size(self.total_transferred)}/{format_size(self.total_size)} {percent}%", COL_BLEU2)
                        else:
                            pass
                    part_number += BATCH_SIZE
            comp_resp = self.app.api_client.upload_multipart_complete(key, upload_id, uploaded_parts)
            if comp_resp.status_code not in [200, 201]:
                if tmp_path: Path(tmp_path).unlink(missing_ok=True)
                return None
            entry_data = {
                "clientMime": "application/octet-stream", "clientName": file_name,
                "filename": key.split("/")[-1], "size": enc_size, 
                "clientExtension": Path(file_name).suffix.lstrip('.'),
                "relativePath": remote_path, "workspaceId": ws_id
            }
            entry_resp = self.app.api_client.create_entry(entry_data)
            if tmp_path: Path(tmp_path).unlink(missing_ok=True) 
            if entry_resp.status_code in [200, 201]:
                 fe = entry_resp.json().get('fileEntry') or entry_resp.json()
                 if fe and fe.get('id'):
                     return {"id": fe["id"], "size": local_info["size"], "mtime": local_info["mtime"], "partial_hash": local_info["partial_hash"]}
            return None
        except Exception as e:
            self.log_ui(f"[{thread_name}] Err Multipart: {e}", "red")
            if tmp_path: Path(tmp_path).unlink(missing_ok=True)
            return None
    def generate_report(self, stats: Dict[str, Any], duration: float, final_status: str) -> str:
        if duration < 1: duration = 1
        speed = stats['bytes'] / duration
        speed_str = format_size(speed) + "/s"
        return (
            f"MIROIR E2EE {final_status}\n\n"
            f"✅ Succès : {stats['success']}\n"
            f"✏️ Renommés : {stats['renamed']}\n"
            f"🗑️ Supprimés : {stats['deleted']}\n"
            f"❌ Échecs : {stats['failed']}\n\n"
            f"📦 Volume : {format_size(stats['bytes'])}\n"
            f"⚡ Vitesse : {speed_str}\n"
            f"⏱️ Durée : {int(duration)}s"
        )
    def _thread_mirror_logic(self, local_folder: str, workspace_id: str, is_dry_run: bool, force_sync: bool) -> None:
        """Logique principale de synchronisation E2EE (Thread dédié)."""
        try:
            self.log_ui(f"--- DÉMARRAGE {self.e2ee_mode} ({'SIMU' if is_dry_run else 'REEL'}) ---", "green")
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
                     self.log_ui("État local réinitialisé.", "yellow")
            cloud_tree = self.load_local_cloud_tree(app_data_state_dir, api_key, workspace_id)
            use_exc = self.app.config_data.get(CONF_KEY_USE_EXCLUSIONS, True)
            local_tree = self.get_local_tree(local_folder, app_data_state_dir, use_exc)
            self.log_ui("Comparaison des arbres...")
            self.update_status_ui("Comparaison...", COL_VERT)
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
                    if is_dry_run: self.log_ui(f"[SIMU] Suppression dossier: {fp}", "red")
                    else: self.log_ui(f"[DEBUG] Suppression dossier: {fp}")
            self.log_ui("Analyse des fichiers...")
            self.update_status_ui("Analyse des fichiers...", COL_VERT)
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
                                new_name = sanitize_filename_for_upload(Path(new_path).name)
                                old_parent = str(Path(old_path).parent)
                                new_parent = str(Path(new_path).parent)
                                if old_parent == new_parent:
                                    if is_dry_run:
                                         self.log_ui(f"[SIMU] Renommage: {old_path} -> {new_path}", "yellow")
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
                remote_target_name = name
                parts = new_p.split("/")
                raw_filename = parts[-1]
                is_zk = (self.e2ee_mode == MODE_E2EE_ZK)
                is_adv = (self.e2ee_mode == MODE_E2EE_ADVANCED)
                if is_zk:
                     enc_full_name = E2EE_encrypt_name(raw_filename, self.e2ee_key)
                     remote_target_name = f"{enc_full_name}.enc"
                elif is_adv:
                     p_raw = Path(raw_filename)
                     base, ext = p_raw.stem, p_raw.suffix
                     enc = E2EE_encrypt_name(base, self.e2ee_key)
                     remote_target_name = f"{enc}{ext}"
                else: 
                     remote_target_name = sanitize_filename_for_upload(name)
                if not self.rename_remote_entry(eid, remote_target_name, api_key):
                    self.log_ui(f"Échec renommage {new_p}", "red")
                    paths_to_upload_later.add(new_p)
                    paths_to_delete_later.add(old_p)
                else:
                    if str(Path(old_p).parent) == str(Path(new_p).parent):
                         files_renamed_count += 1
                         self.log_ui(f"Renommé: {old_p} -> {new_p}", "yellow")
                    else:
                         files_moved_count += 1
                         self.log_ui(f"Déplacé: {old_p} -> {new_p}", "yellow")
            files_to_delete_ids = []
            for p in paths_to_delete_later:
                if p in cloud_tree["files"]:
                    files_to_delete_ids.append(cloud_tree["files"][p]["id"])
                    del cloud_tree["files"][p]
                    if is_dry_run: self.log_ui(f"[SIMU] Suppression fichier: {p}", "red")
                    else: self.log_ui(f"[DEBUG] Suppr: {p}")
            for p in paths_to_check:
                l_info = local_tree["files"][p]
                c_info = cloud_tree["files"][p]
                if l_info['size'] != c_info.get('size') or l_info['partial_hash'] != c_info.get('partial_hash'):
                    self.log_ui(f"Modifié: {p}", "yellow")
                    files_to_upload.append(p)
            for p in paths_to_upload_later: files_to_upload.append(p)
            if is_dry_run:
                for p in files_to_upload: self.log_ui(f"[SIMU] Upload: {p}")
                self.log_ui("--- FIN SIMULATION ---", "yellow")
                return
            total = len(files_to_upload)
            
            save_interval = 5
            if total > 10000: save_interval = 1000
            elif total > 2000: save_interval = 200
            elif total > 200: save_interval = 50
            
            self.log_ui(f"Fichiers à uploader: {total} (Sauvegarde état tous les {save_interval})")
            self.total_size = 0
            self.total_transferred = 0
            for p in files_to_upload:
                self.total_size += local_tree["files"][p]["size"]
            self.update_status_ui(f"Modifications: {total} fichier(s)", COL_VIOLET)
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
                         remote_tree_path_enc = self._calculate_remote_path(tree_rel_path, is_folder=False)
                         res_tree = self.upload_file_router_e2ee(tree_info, remote_tree_path_enc, api_key, workspace_id, "System")
                         if res_tree: break
                         time.sleep(2)
                    if res_tree:
                         self.log_ui("État sauvegardé sur le cloud (Chiffré).", "green")
            if self.e2ee_key:
                 self.save_local_cloud_tree(cloud_tree, app_data_state_dir, encrypt=True)
                 self.log_ui("Fichier d'état local chiffré.", "cyan")
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
            self.log_ui(f"ERREUR FATALE: {e}", "red")
            import traceback
            traceback.print_exc()
        finally:
            def _reset(): self._set_ui_running(False)
            self.app.loop.call_soon_threadsafe(_reset)