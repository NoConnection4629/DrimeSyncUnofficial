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
    API_BASE_URL, HTTP_TIMEOUT, MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK, 
    E2EE_CRYPTO_ALGO, SYNC_STATE_FOLDER_NAME, CLOUD_TREE_FILE_NAME, EXCLUDE_FILE_NAME, 
    PARTIAL_HASH_CHUNK_SIZE, PART_UPLOAD_RETRIES, CHUNK_SIZE, BATCH_SIZE,
    CONF_KEY_API_KEY, CONF_KEY_WORKERS, CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD,
    ANDROID_DOWNLOAD_PATH
)
from drimesyncunofficial.utils import format_size, sanitize_filename_for_upload, get_salt_path, derive_key, generate_or_load_salt
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background
from drimesyncunofficial.utils import E2EE_encrypt_file, E2EE_decrypt_file, E2EE_encrypt_name, get_remote_path_for_tree_file, load_exclusion_patterns, E2EE_encrypt_bytes, E2EE_decrypt_bytes, truncate_path_smart
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.i18n import tr
MULTIPART_THRESHOLD = 30 * 1024 * 1024
simple_upload_limiter: Optional[threading.Semaphore] = None
from drimesyncunofficial.base_transfer_manager import BaseTransferManager

class ManualUploadE2EEManager(BaseTransferManager):
    """
    Gestionnaire d'Upload Manuel avec Chiffrement de Bout en Bout (E2EE).
    Synchronise un dossier local vers un workspace distant en chiffrant tout à la volée.
    """
    def __init__(self, app: Any):
        super().__init__(app)
        self.selection: List[str] = [] 
        self.window: Optional[toga.Window] = None
        self.lbl_warning_ws: Optional[toga.Label] = None
        self.lbl_conflict_warning: Optional[toga.Label] = None
                                      
        self.log_output: Optional[toga.MultilineTextInput] = None 
        self.txt_logs: Optional[toga.MultilineTextInput] = None
        self.btn_sync: Optional[toga.Button] = None
        self.btn_simu: Optional[toga.Button] = None
        self.btn_force: Optional[toga.Button] = None
                                                 
                                                               
        self.btn_send: Optional[toga.Button] = None
        self.selection_ws: Optional[toga.Selection] = None
        self.lbl_selection_count: Optional[toga.Label] = None
        self.e2ee_mode: str = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
        self.e2ee_password: str = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
        self.e2ee_key: Optional[bytes] = None 
        
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
             asyncio.ensure_future(self._show_error_dialog_async(tr("title_warning", "Configuration Requise"), tr("sec_warn_passwd_req", "Mot de passe E2EE manquant.")))
             return
        
        try:
             salt = generate_or_load_salt(self.app.paths)
             if not salt:
                 asyncio.ensure_future(self._show_error_dialog_async(tr("title_error", "Erreur Sel"), "Impossible de charger le sel."))
                 return
             self.e2ee_key = derive_key(str(self.e2ee_password), salt)
        except Exception as e:
             asyncio.ensure_future(self._show_error_dialog_async(tr("title_error", "Erreur Clé"), f"Détail: {e}"))
             return

        mode_detail_label = {
            MODE_E2EE_STANDARD: f"E2EE - {tr('mode_standard', 'Standard')} ({E2EE_CRYPTO_ALGO})",
            MODE_E2EE_ADVANCED: f"E2EE - {tr('mode_advanced', 'Advanced')} ({E2EE_CRYPTO_ALGO})",
            MODE_E2EE_ZK: f"E2EE - {tr('mode_zk', 'Zero Knowledge')} ({E2EE_CRYPTO_ALGO})",
        }.get(self.e2ee_mode, "MODE INCONNU")

        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))
        
        box.add(create_back_button(self.go_back))
        box.add(toga.Label(tr("up_manual_e2ee_title", "UPLOAD MANUEL (E2EE)"), style=Pack(font_weight=BOLD, color=COL_VERT, margin_bottom=5, font_size=12)))
        box.add(toga.Label(tr("up_manual_subtitle", "Sélectionnez des fichiers ou dossiers à chiffrer et envoyer."), style=Pack(font_size=10, margin_bottom=20, color=COL_TEXT_GRIS)))
        
        box.add(toga.Label(tr("up_dest_label", "Destination (Workspace) :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        items = [tr("dl_personal_space", "Espace Personnel (ID: 0)")]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: items.append(f"{ws['name']} (ID: {ws['id']})")
        self.selection_ws = toga.Selection(items=items, on_change=self.update_warnings, style=Pack(width=220, margin_bottom=10))
        box.add(self.selection_ws)

        self.lbl_conflict_warning = toga.Label(tr("up_warn_conflict", "⚠️ CONFLIT : Workspace utilisé par un MIRROIR."), style=Pack(font_size=8, color=COL_ROUGE, font_weight=BOLD, margin_bottom=20, visibility='hidden', flex=1))
        box.add(self.lbl_conflict_warning)

        box.add(toga.Label(tr("up_source_label", "Source :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.lbl_selection_count = toga.Label(tr("up_select_none", "Aucune sélection"), style=Pack(margin_bottom=5, color='gray', flex=1))
        box.add(self.lbl_selection_count)

        row_select = toga.Box(style=Pack(direction=ROW, margin_bottom=20))
        row_select.add(toga.Button(tr("up_btn_choose_files", "📄 Fichiers"), on_press=self.action_choose_files, style=Pack(flex=1, margin_right=5)))
        row_select.add(toga.Button(tr("up_btn_choose_folder", "📂 Dossier"), on_press=self.action_choose_folder, style=Pack(flex=1, margin_left=5)))
        box.add(row_select)

        self.box_actions_container = toga.Box(style=Pack(direction=COLUMN))
        self.btn_send = toga.Button(tr("up_btn_encrypt_send", "CHIFFRER & ENVOYER"), on_press=self.action_start_upload, style=Pack(background_color=COL_VERT, color='white', font_weight=BOLD, height=50, margin_bottom=5, flex=1))
        self.btn_simu = toga.Button(tr("up_btn_simu", "Simulation"), on_press=self.action_start_simu, style=Pack(background_color=COL_JAUNE, color='white', height=40, margin_bottom=5, flex=1))
        self.box_actions_container.add(self.btn_send)
        self.box_actions_container.add(self.btn_simu)
        box.add(self.box_actions_container)

        self.box_controls = toga.Box(style=Pack(direction=ROW, visibility='hidden', height=0, flex=1))
        self.btn_pause = toga.Button(tr("up_btn_pause", "⏸️ Pause"), on_press=self.action_toggle_pause, style=Pack(flex=1, margin_right=5, height=50, background_color=COL_JAUNE, color='white', visibility='hidden'))
        self.btn_cancel = toga.Button(tr("up_btn_cancel_all", "⏹️ Annuler Tout"), on_press=self.action_cancel, style=Pack(flex=1, margin_left=5, height=50, background_color=COL_ROUGE, color='white', font_weight=BOLD, visibility='hidden'))
        self.box_controls.add(self.btn_pause)
        self.box_controls.add(self.btn_cancel)
        box.add(self.box_controls)

        self.lbl_progress = toga.Label("", style=Pack(font_weight=BOLD, margin_bottom=5, font_size=10, color=COL_JAUNE, flex=1))
        box.add(self.lbl_progress)

        box.add(toga.Label(tr("up_log_title", "Log :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.txt_logs = create_logs_box(height=150, margin=5)
        self.log_output = self.txt_logs 
        box.add(self.txt_logs)

        self.update_warnings(None)  
        self._set_ui_running(False)

        main_container.content = box
        self.main_box_content = main_container 
        self.app.changer_ecran(main_container)

    def go_back(self, widget):
        if self.is_running: return
        self.app.retour_arriere(widget)

    def action_choose_files(self, widget):
        if self.app.is_mobile:
            def on_file_picked(result_paths):
                self.app.main_window.content = self.main_box_content
                if result_paths:
                    self.selection.extend([str(p) for p in result_paths])
                    self.update_selection_label()
                    self.log_ui(f"{tr('dl_type_file', 'Fichier')} {tr('status_added', 'ajouté')} : {result_paths[0]}", "green")
                else:
                    self.log_ui(tr("dl_selection_cancelled", "Sélection annulée."), "yellow")
            browser = AndroidFileBrowser(self.app, on_file_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=False)
            self.app.main_window.content = browser
        else:
            self.action_choose_files_desktop(widget)

    def action_choose_files_desktop(self, widget):
        async def _ask():
            files = await self.app.main_window.dialog(toga.OpenFileDialog(tr("up_btn_choose_files", "Choisir des fichiers"), multiple_select=True))
            if files:
                self.selection.extend([str(f) for f in files])
                self.update_selection_label()
        asyncio.ensure_future(_ask())

    def action_choose_folder(self, widget):
        if self.app.is_mobile:
            def on_folder_picked(result_path):
                self.app.main_window.content = self.main_box_content
                if result_path:
                    self.selection.append(str(result_path))
                    self.update_selection_label()
                    self.log_ui(f"{tr('browser_type_folder', 'Dossier')} {tr('status_added', 'ajouté')} : {result_path}", "green")
                else:
                    self.log_ui(tr("dl_selection_cancelled", "Sélection annulée."), "yellow")
            browser = AndroidFileBrowser(self.app, on_folder_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
            self.app.main_window.content = browser
        else:
            self.action_choose_folder_desktop(widget)
    
    def action_choose_folder_desktop(self, widget):
        async def _ask():
            folder = await self.app.main_window.dialog(toga.SelectFolderDialog(tr("up_btn_choose_folder", "Choisir un dossier")))
            if folder:
                self.selection.append(str(folder))
                self.update_selection_label()
        asyncio.ensure_future(_ask())

    def update_selection_label(self):
        count = len(self.selection)
        self.lbl_selection_count.text = tr("up_select_count", f"{count} élément(s) sélectionné(s)").format(count=count)

    def _get_ws_id(self):
        val = self.selection_ws.value
        if "ID: 0" in val: return "0"
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return "0"

    def update_warnings(self, widget: Any) -> None:
        if not self.lbl_conflict_warning: return
        sel = self._get_ws_id()
        mirror_std_id = self.app.config_data.get('workspace_standard_id', '0')
        mirror_e2ee_id = self.app.config_data.get('workspace_e2ee_id', '0')
        if sel == mirror_std_id or sel == mirror_e2ee_id:
            self.lbl_conflict_warning.style.visibility = 'visible'
        else:
            self.lbl_conflict_warning.style.visibility = 'hidden'

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

    async def action_start_simu(self, widget):
        await self.launch_upload(is_dry_run=True)

    async def action_start_upload(self, widget):
        await self.launch_upload(is_dry_run=False)
        
    async def launch_upload(self, is_dry_run: bool):
        if not self.selection:
            await self.app.main_window.dialog(toga.InfoDialog(tr("title_info", "Info"), tr("dl_msg_select_items", "Veuillez sélectionner des fichiers.")))
            return
        self.stop_event.clear()
        self.txt_logs.value = ""
        self._set_ui_running(True)
        ws_id = self._get_ws_id()
        api_key = self.app.config_data.get(CONF_KEY_API_KEY, '')
        run_in_background(self._thread_logic, ws_id, api_key, is_dry_run)
    def _thread_logic(self, ws_id, api_key, is_dry_run):
        try:
            self.log_ui(f"--- {tr('up_manual_e2ee_title', 'DÉMARRAGE E2EE')} {'[SIMU]' if is_dry_run else ''} ---", "green")
            start_time = time.time()
            self.log_ui(tr("init_status", "Analyse de la sélection..."))
            local_files = self.get_local_manual_selection(self.selection)
            total_files = len(local_files)
            self.total_size = sum(f['size'] for f in local_files.values())
            self.total_transferred = 0
            self.log_ui(f"{tr('dl_type_file', 'Fichiers')}: {total_files} | {tr('dl_col_size', 'Taille')}: {format_size(self.total_size)}")
            upload_queue = Queue()
            result_queue = Queue()
            for rel, info in local_files.items():
                upload_queue.put((rel, info))
            nb_workers = int(self.app.config_data.get(CONF_KEY_WORKERS, 3))
            global simple_upload_limiter
            simple_upload_limiter = threading.Semaphore(nb_workers)
            self.last_text = tr("dl_status_preparing", "Préparation...")
            run_in_background(self._spinner_loop)
            workers = []
            for i in range(nb_workers):
                t = run_in_background(
                    self.upload_worker_manual, 
                    upload_queue, 
                    result_queue, 
                    api_key, 
                    ws_id, 
                    is_dry_run
                )
                t.name = f"Worker-ManualE2EE-{i+1}"
                workers.append(t)
            stats = {'success': 0, 'failed': 0, 'skipped': 0, 'bytes': 0}
            processed = 0
            while processed < total_files:
                if self.stop_event.is_set(): break
                rel_path, res, s_retries, m_retries = result_queue.get()
                processed += 1
                if res and not isinstance(res, dict): 
                     stats['skipped'] += 1
                     self.log_ui(f"[SIMU] {rel_path}")
                elif res and 'id' in res:
                    stats['success'] += 1
                    stats['bytes'] += res.get('size', 0)
                                                                                                     
                    self.log_ui(f"{tr('transfer_status_success', 'Succès')}: {rel_path}")
                else:
                    stats['failed'] += 1
                    self.log_ui(f"{tr('transfer_status_failed', 'Échec')}: {rel_path}", "red")
                                                                                                               
                                                                                                                                             

                continue
            self.check_wait_pause()
            if self.stop_event.is_set():
                self.log_ui(f"--- {tr('transfer_status_cancelled', 'ANNULÉ')} ---", "red")
            else:
                self.log_ui(f"--- {tr('transfer_status_done', 'TERMINÉ')} ---", "green")
                duration = time.time() - start_time
                report = self.generate_report(stats, duration, tr('transfer_status_done', 'TERMINÉ'))
                async def show_report():
                    await self.app.main_window.dialog(toga.InfoDialog(tr("dl_report_title", "Rapport"), report))
                asyncio.run_coroutine_threadsafe(show_report(), self.app.loop)
        except Exception as e:
            self.log_ui(f"{tr('title_error', 'ERREUR')}: {e}", "red")
        finally:
            def _reset(): self._set_ui_running(False)
            self.app.loop.call_soon_threadsafe(_reset)
    def _calculate_remote_path(self, rel_path: str, is_folder: bool = False) -> str:
        """
        Calcule le chemin distant chiffré selon le mode E2EE.
        Aligné sur la logique du Miroir.
        """
        parts = rel_path.replace("\\", "/").split('/')
        enc_parts = []
        for i, p in enumerate(parts):
            is_last = (i == len(parts) - 1)
            is_file_item = is_last and not is_folder
            
            if self.e2ee_mode == MODE_E2EE_ZK:
                                                                      
                enc_name = E2EE_encrypt_name(p, self.e2ee_key)
                if is_file_item:
                    enc_parts.append(f"{enc_name}.enc")
                else:
                    enc_parts.append(enc_name)
                    
            elif self.e2ee_mode == MODE_E2EE_ADVANCED:
                                                                                           
                if is_file_item:
                    path_obj = Path(p)
                    enc_stem = E2EE_encrypt_name(path_obj.stem, self.e2ee_key)
                    enc_parts.append(f"{enc_stem}{path_obj.suffix}")
                else:
                    enc_parts.append(sanitize_filename_for_upload(p))
                    
            else: 
                                                      
                                                                                          
                if is_file_item:
                    enc_parts.append(f"{p}.enc")
                else:
                    enc_parts.append(sanitize_filename_for_upload(p))
                
        return '/'.join(enc_parts)
    def upload_worker_manual(self, upload_queue: Queue, result_queue: Queue, api_key: str, workspace_id: str, is_dry_run: bool) -> None:
        """Worker thread pour l'upload E2EE."""
        thread_name = threading.current_thread().name
        while True:
            try: 
                rel_path, local_info = upload_queue.get_nowait()
            except: 
                break
            if self.stop_event.is_set():
                upload_queue.task_done()
                continue
            if not self.check_wait_pause():
                upload_queue.task_done()
                continue
            self.log_ui(f"[DEBUG] [{thread_name}] Prise en charge: {rel_path}")
            if is_dry_run:
                remote_path = self._calculate_remote_path(rel_path, is_folder=False)
                self.log_ui(f"[SIMU] {rel_path} -> {remote_path}")
                result_queue.put((rel_path, "simulated", 0, 0))
                upload_queue.task_done()
                continue
            remote_path = self._calculate_remote_path(rel_path, is_folder=False)
            result = None
            total_simple_retries = 0
            total_multipart_retries = 0
            for attempt in range(PART_UPLOAD_RETRIES):
                is_simple = (local_info["size"] <= MULTIPART_THRESHOLD)
                if is_simple and simple_upload_limiter:
                    simple_upload_limiter.acquire()
                try:
                    if is_simple:
                        result = self.upload_simple_e2ee(local_info, remote_path, api_key, workspace_id, thread_name)
                    else:
                        result = self.upload_multipart_e2ee(local_info, remote_path, api_key, workspace_id, thread_name)
                except Exception as e:
                    self.log_ui(f"Exception worker: {e}")
                finally:
                    if is_simple and simple_upload_limiter:
                        simple_upload_limiter.release()
                if result is not None:
                    if isinstance(result, dict) and result.get("error"):
                        break
                    break
                if attempt < (PART_UPLOAD_RETRIES - 1):
                    if is_simple: total_simple_retries += 1
                    else: total_multipart_retries += 1
                    time.sleep(5)
            result_queue.put( (rel_path, result, total_simple_retries, total_multipart_retries) )
            upload_queue.task_done()
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
            if resp.status_code == 403:
                return {"error": "403_FORBIDDEN"}
            if resp.status_code == 500:
                return {"error": "500_SERVER_ERROR"}
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
                    if not self.check_wait_pause(): raise Exception("Cancelled")
                    batch_end = min(part_number + BATCH_SIZE - 1, num_parts)
                    batch_nums = list(range(part_number, batch_end + 1))
                    sign_resp = self.app.api_client.upload_multipart_sign_batch(key, upload_id, batch_nums)
                    if sign_resp.status_code not in [200, 201]:
                        if tmp_path: Path(tmp_path).unlink(missing_ok=True)
                        return None
                    urls_map = {u['partNumber']: u['url'] for u in sign_resp.json()['urls']}
                    for pn in batch_nums:
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
            
            comp_data = comp_resp.json()
            fe_direct = comp_data.get('fileEntry') or comp_data
            if fe_direct and fe_direct.get('id') and fe_direct.get('name'):
                 if tmp_path: Path(tmp_path).unlink(missing_ok=True)
                 return {"id": fe_direct["id"], "size": local_info["size"], "mtime": local_info["mtime"], "partial_hash": local_info["partial_hash"]}
            
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
            f"UPLOAD MANUEL E2EE {final_status}\n\n"
            f"✅ {tr('transfer_status_success', 'Succès')} : {stats['success']}\n"
            f"❌ {tr('transfer_status_failed', 'Échecs')} : {stats['failed']}\n"
            f"⏭️ {tr('up_btn_simu', 'Simulé')} : {stats['skipped']}\n\n"
            f"📦 Volume : {format_size(stats['bytes'])}\n"
            f"⚡ {tr('speed', 'Vitesse')} : {speed_str}\n"
            f"⏱️ {tr('duration', 'Durée')} : {int(duration)}s"
        )
    def get_partial_hash(self, file_path: Union[str, Path], file_size: int) -> Optional[str]:
        m = hashlib.md5()
        m.update(str(file_size).encode('utf-8'))
        try:
            with open(file_path, "rb") as f:
                if file_size <= PARTIAL_HASH_CHUNK_SIZE * 2: m.update(f.read())
                else:
                    f.seek(0)
                    m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
                    f.seek(-PARTIAL_HASH_CHUNK_SIZE, os.SEEK_END)
                    m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
            return m.hexdigest()
        except: return None
    def get_local_manual_selection(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        local_files = {}
        for item_path_str in paths:
            try:
                item_path = Path(str(item_path_str)).resolve()
                if item_path.is_file():
                    rel_path = item_path.name
                    try:
                        stats = item_path.stat()
                        if stats.st_size >= 0: 
                            ph = self.get_partial_hash(item_path, stats.st_size)
                            if ph: 
                                local_files[rel_path] = {
                                    "full_path": str(item_path), 
                                    "size": stats.st_size, 
                                    "mtime": stats.st_mtime, 
                                    "partial_hash": ph, 
                                    "root": str(item_path)
                                }
                    except Exception as e:
                        self.log_ui(f"Erreur Lecture: {item_path.name} - {e}", "red")
                elif item_path.is_dir():
                    root_name = item_path.name
                    try:
                        for full_path in item_path.rglob('*'):
                            if full_path.is_file():
                                try:
                                    rel_path_suffix = str(full_path.relative_to(item_path)).replace("\\", "/")
                                    rel_path = f"{root_name}/{rel_path_suffix}"
                                    stats = full_path.stat()
                                    ph = self.get_partial_hash(full_path, stats.st_size)
                                    if ph: 
                                        local_files[rel_path] = {
                                            "full_path": str(full_path), 
                                            "size": stats.st_size, 
                                            "mtime": stats.st_mtime, 
                                            "partial_hash": ph, 
                                            "root": str(item_path)
                                        }
                                except Exception:
                                    continue
                    except OSError as e:
                        self.log_ui(f"Impossible de lire le dossier (Restriction OS): {root_name}", "red")
            except Exception as main_e:
                self.log_ui(f"Erreur chemin global: {main_e}", "red")
        return local_files