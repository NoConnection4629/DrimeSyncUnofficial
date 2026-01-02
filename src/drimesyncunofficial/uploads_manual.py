import toga
import asyncio
import json
import os
import time
import threading
import math
import mimetypes
import hashlib
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable
from queue import Queue
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import (
    COL_GRIS, COL_TEXT_GRIS, COL_VERT, COL_BLEU, COL_ROUGE, COL_JAUNE, COL_VIOLET, COL_BLEU2, 
    API_BASE_URL, HTTP_TIMEOUT, PARTIAL_HASH_CHUNK_SIZE,
    CONF_KEY_API_KEY, CONF_KEY_WORKERS, CHUNK_SIZE, BATCH_SIZE, PART_UPLOAD_RETRIES,
    ANDROID_DOWNLOAD_PATH
)
from drimesyncunofficial.utils import format_size, sanitize_filename_for_upload, load_exclusion_patterns, truncate_path_smart
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.i18n import tr
MULTIPART_THRESHOLD = 30 * 1024 * 1024 
simple_upload_limiter: Optional[threading.Semaphore] = None
from drimesyncunofficial.base_transfer_manager import BaseTransferManager

class ManualUploadManager(BaseTransferManager):
    """
    Gestionnaire d'Upload Manuel (Mode Standard - Non Chiffré).
    Permet de sélectionner des fichiers/dossiers locaux et de les envoyer vers un workspace Drime.
    Gère la file d'attente, le multi-threading et l'affichage de la progression.
    """
    def __init__(self, app: Any):
        super().__init__(app)
        self.selection: List[str] = [] 
        self.window: Optional[toga.Window] = None
        self.lbl_conflict_warning: Optional[toga.Label] = None
        self.txt_logs: Optional[toga.MultilineTextInput] = None
                                      
        
                                                           
        
        self.total_size: int = 0
        self.total_transferred: int = 0
        self.progress_lock: threading.Lock = threading.Lock()
        
        self.btn_send: Optional[toga.Button] = None
        self.btn_simu: Optional[toga.Button] = None
        self.selection_ws: Optional[toga.Selection] = None
        self.lbl_selection_count: Optional[toga.Label] = None
        self.main_box_content = None

    def show(self) -> None:
        """Affiche l'interface d'upload manuel."""
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))
        box.add(create_back_button(self.go_back, margin_bottom=20))
        box.add(toga.Label(tr("title_manual_upload_std", "UPLOAD MANUEL (STANDARD)"), style=Pack(font_weight=BOLD, color=COL_BLEU, margin_bottom=5, font_size=12)))
        box.add(toga.Label(tr("subtitle_select_files", "Sélectionnez des fichiers ou dossiers à envoyer."), style=Pack(font_size=10, margin_bottom=20, color=COL_TEXT_GRIS)))
        box.add(toga.Label(tr("label_destination", "Destination :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        items = [tr("personal_space", "Espace Personnel (ID: 0)")]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: items.append(f"{ws['name']} (ID: {ws['id']})")
        self.selection_ws = toga.Selection(items=items, on_change=self.update_warnings, style=Pack(width=220, margin_bottom=10))
        box.add(self.selection_ws)
        self.lbl_conflict_warning = toga.Label(tr("warning_conflict", "⚠️ CONFLIT : Workspace utilisé par un MIRROIR. Cela va désynchroniser le miroir."), style=Pack(font_size=8, color=COL_ROUGE, font_weight=BOLD, margin_bottom=20, visibility='hidden', flex=1))
        box.add(self.lbl_conflict_warning)
        box.add(toga.Label(tr("label_source", "Source :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.lbl_selection_count = toga.Label(tr("no_selection", "Aucune sélection"), style=Pack(margin_bottom=5, color='gray', flex=1))
        box.add(self.lbl_selection_count)
        row_select = toga.Box(style=Pack(direction=ROW, margin_bottom=20))
        row_select.add(toga.Button(tr("btn_files", "📄 Fichiers"), on_press=self.action_choose_files, style=Pack(flex=1, margin_right=5)))
        row_select.add(toga.Button(tr("btn_folder", "📂 Dossier"), on_press=self.action_choose_folder, style=Pack(flex=1, margin_left=5)))
        box.add(row_select)
        
                                                        
        self.box_actions_container = toga.Box(style=Pack(direction=COLUMN))
        self.btn_send = toga.Button(tr("btn_send", "ENVOYER"), on_press=self.action_start_upload, style=Pack(background_color=COL_BLEU, color='white', font_weight=BOLD, height=50, margin_bottom=5, flex=1))
        self.btn_simu = toga.Button(tr("btn_simulation", "Simulation"), on_press=self.action_start_simu, style=Pack(background_color=COL_JAUNE, color='white', height=40, margin_bottom=5, flex=1))
        self.box_actions_container.add(self.btn_send)
        self.box_actions_container.add(self.btn_simu)
        box.add(self.box_actions_container)
        
                                                  
        self.box_controls = toga.Box(style=Pack(direction=ROW, visibility='hidden', height=0))
        self.btn_pause = toga.Button(tr("btn_pause", "⏸️ Pause"), on_press=self.action_toggle_pause, style=Pack(flex=1, margin_right=5, height=50, background_color=COL_JAUNE, color='white', visibility='hidden'))
        self.btn_cancel = toga.Button(tr("btn_cancel", "⏹️ Annuler"), on_press=self.action_cancel, style=Pack(flex=1, margin_left=5, height=50, background_color=COL_ROUGE, color='white', font_weight=BOLD, visibility='hidden'))
        self.box_controls.add(self.btn_pause)
        self.box_controls.add(self.btn_cancel)
        box.add(self.box_controls)
        
        self.lbl_progress = toga.Label("", style=Pack(font_weight=BOLD, margin_bottom=5, font_size=10, color=COL_JAUNE, flex=1))
        box.add(self.lbl_progress)
        box.add(toga.Label(tr("label_log", "Log :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.txt_logs = create_logs_box(font_size=8, height=150)
        box.add(self.txt_logs)
        self.update_warnings(None)
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
                    self.log_ui(f"{tr('log_file_added', 'Fichier ajouté :')} {result_paths[0]}", "green")
                else:
                    self.log_ui(tr("log_selection_cancelled", "Sélection annulée."), "yellow")
            browser = AndroidFileBrowser(self.app, on_file_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=False)
            self.app.main_window.content = browser
        else:
            self.action_choose_files_desktop(widget)

    def action_choose_files_desktop(self, widget):
        async def _ask():
            files = await self.app.main_window.dialog(toga.OpenFileDialog(tr("title_choose_files", "Choisir des fichiers"), multiple_select=True))
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
                    self.log_ui(f"{tr('log_folder_added', 'Dossier ajouté :')} {result_path}", "green")
                else:
                    self.log_ui(tr("log_selection_cancelled", "Sélection annulée."), "yellow")
            browser = AndroidFileBrowser(self.app, on_folder_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
            self.app.main_window.content = browser
        else:
            self.action_choose_folder_desktop(widget)

    def action_choose_folder_desktop(self, widget):
        async def _ask():
            folder = await self.app.main_window.dialog(toga.SelectFolderDialog(tr("title_choose_folder", "Choisir un dossier")))
            if folder:
                self.selection.append(str(folder))
                self.update_selection_label()
        asyncio.ensure_future(_ask())

    def update_selection_label(self):
        count = len(self.selection)
        self.lbl_selection_count.text = f"{count} {tr('label_elements_selected', 'élément(s) sélectionné(s)')}"

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
    def action_toggle_pause(self, widget):
        if not self.is_running: return
        if self.is_paused:
            self.is_paused = False
            self.btn_pause.text = tr("btn_pause", "⏸️ Pause")
            self.btn_pause.style.background_color = COL_JAUNE
            self.log_ui(tr("log_resumed", "Reprise..."))
        else:
            self.is_paused = True
            self.btn_pause.text = tr("btn_resume", "▶️ Reprendre")
            self.btn_pause.style.background_color = COL_VERT
            self.log_ui(tr("log_paused", "PAUSE..."))
    async def action_cancel(self, widget):
        if not self.is_running: return
        if await self.app.main_window.dialog(toga.QuestionDialog(tr("title_confirmation", "Confirmation"), tr("confirm_cancel_upload", "Annuler l'upload ?"))):
            self.stop_event.set()
            self.log_ui(tr("log_cancellation_in_progress", "ANNULATION EN COURS..."), "red")
    async def action_start_simu(self, widget):
        await self.launch_upload(is_dry_run=True)
    async def action_start_upload(self, widget):
        await self.launch_upload(is_dry_run=False)
    async def launch_upload(self, is_dry_run: bool):
        if not self.selection:
            await self.app.main_window.dialog(toga.InfoDialog(tr("title_info", "Info"), tr("msg_select_files", "Veuillez sélectionner des fichiers.")))
            return
        self.stop_event.clear()
        self.txt_logs.value = ""
        self._set_ui_running(True)
        ws_id = self._get_ws_id()
        api_key = self.app.config_data.get(CONF_KEY_API_KEY, '')
        self.last_text = tr("status_preparing", "Préparation...")
        run_in_background(self._thread_logic, ws_id, api_key, is_dry_run)
        run_in_background(self._spinner_loop)
    def _thread_logic(self, ws_id, api_key, is_dry_run):
        try:
            start_str = tr("log_start_simu", "--- DÉMARRAGE SIMU ---") if is_dry_run else tr("log_start", "--- DÉMARRAGE ---")
            self.log_ui(start_str, "green")
            start_time = time.time()
            self.log_ui(tr("log_analyzing_selection", "Analyse de la sélection..."))
            local_files = self.get_local_manual_selection(self.selection)
            total_files = len(local_files)
            self.total_size = sum(f['size'] for f in local_files.values())
            self.total_transferred = 0
            self.log_ui(f"{tr('log_stats_files', 'Fichiers')}: {total_files} | {tr('log_stats_size', 'Taille')}: {format_size(self.total_size)}")
            upload_queue = Queue()
            result_queue = Queue()
            for rel, info in local_files.items():
                upload_queue.put((rel, info))
            nb_workers = int(self.app.config_data.get(CONF_KEY_WORKERS, 3))
            global simple_upload_limiter
            simple_upload_limiter = threading.Semaphore(nb_workers)
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
                t.name = f"Worker-Manual-{i+1}"
                workers.append(t)
            stats = {'success': 0, 'failed': 0, 'skipped': 0, 'bytes': 0}
            processed = 0
            while processed < total_files:
                if self.stop_event.is_set(): break
                rel_path, res, s_retries, m_retries = result_queue.get()
                processed += 1
                if res and not isinstance(res, dict): 
                     stats['skipped'] += 1
                     self.log_ui(f"[{tr('tag_simu', 'SIMU')}] {rel_path}")
                elif res and 'id' in res:
                    stats['success'] += 1
                    stats['bytes'] += res.get('size', 0)
                                                                                                     
                    self.log_ui(f"{tr('log_success', 'Succès')}: {rel_path}")
                else:
                    stats['failed'] += 1
                    self.log_ui(f"{tr('log_failure', 'Échec')}: {rel_path}", "red")
                                                                                                               
                                                                                                                                             

                continue
            while self.is_paused and not self.stop_event.is_set(): 
                time.sleep(0.5)
            if self.stop_event.is_set():
                self.log_ui(tr("log_cancelled_footer", "--- ANNULÉ ---"), "red")
            else:
                self.log_ui(tr("log_finished_footer", "--- TERMINÉ ---"), "green")
                duration = time.time() - start_time
                report = self.generate_report(stats, duration, tr("status_finished", "TERMINÉ"))
                async def show_report():
                    await self.app.main_window.dialog(toga.InfoDialog(tr("title_report", "Rapport"), report))
                asyncio.run_coroutine_threadsafe(show_report(), self.app.loop)
        except Exception as e:
            self.log_ui(f"{tr('log_error_generic', 'ERREUR')}: {e}", "red")
        finally:
            def _reset(): self._set_ui_running(False)
            self.app.loop.call_soon_threadsafe(_reset)
    def upload_worker_manual(self, upload_queue: Queue, result_queue: Queue, api_key: str, workspace_id: str, is_dry_run: bool) -> None:
        """
        Worker thread générique.
        Récupère les tâches depuis la queue et tente l'upload (avec retries).
        """
        thread_name = threading.current_thread().name
        while True:
            try: 
                rel_path, local_info = upload_queue.get_nowait()
            except: 
                break
            if self.stop_event.is_set():
                upload_queue.task_done()
                continue
            while self.is_paused and not self.stop_event.is_set(): 
                time.sleep(0.5)
            self.log_ui(f"[DEBUG] [{thread_name}] {tr('log_taking_over', 'Prise en charge')}: {rel_path}")
            if is_dry_run:
                result_queue.put((rel_path, "simulated", 0, 0))
                upload_queue.task_done()
                continue
            path_parts = rel_path.split('/')
            renamed_parts = [sanitize_filename_for_upload(p) for p in path_parts]
            cloud_rel_path = '/'.join(renamed_parts)
            if rel_path != cloud_rel_path:
                msg_bug = tr('log_bug_workaround', "Contournement bug '0' généralisé")
                self.log_ui(f"[yellow]{msg_bug}: {rel_path} -> {cloud_rel_path}[/yellow]")
                                               
            def check_status():
                               
                while self.is_paused and not self.stop_event.is_set():
                    time.sleep(0.5)
                return not self.stop_event.is_set()

            def progress_cb(chunk_size):
                with self.progress_lock:
                    self.total_transferred += chunk_size
                    percent = int((self.total_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                    self.update_status_ui(f"{tr('status_uploading', 'Upload')} {format_size(self.total_transferred)}/{format_size(self.total_size)} {percent}%", COL_BLEU2)

            for attempt in range(PART_UPLOAD_RETRIES):
                                                                                                     
                                                      
                try:
                    res = self.app.api_client.upload_file(
                        file_path=local_info["full_path"],
                        workspace_id=workspace_id,
                        relative_path=cloud_rel_path,
                        progress_callback=progress_cb,
                        check_status_callback=check_status
                    )
                    
                            
                    result_queue.put( (rel_path, res, 0, 0) )
                    break
                    
                except Exception as e:
                                     
                    err_msg = str(e)
                    if "403" in err_msg or "Interdit" in err_msg:
                        self.log_ui(f"[red]{tr('log_stop_attempts_403', 'Arrêt des tentatives pour')} {rel_path} (403 Forbidden)[/red]")
                        result_queue.put( (rel_path, {'error': '403_FORBIDDEN'}, 0, 0) )
                        break
                    
                    if attempt < (PART_UPLOAD_RETRIES - 1):
                        self.log_ui(f"[yellow][{thread_name}] {tr('log_retry', 'Re-tentative')} {attempt+1}: {e}[/yellow]")
                        time.sleep(5)
                    else:
                        self.log_ui(f"[red]{tr('log_final_failure', 'Échec final pour')} {rel_path}: {e}[/red]")
                        result_queue.put( (rel_path, None, 0, 0) )
            
            upload_queue.task_done()
    def generate_report(self, stats: Dict[str, Any], duration: float, final_status: str) -> str:
        if duration < 1: duration = 1
        speed = stats['bytes'] / duration
        speed_str = format_size(speed) + "/s"
        return (
            f"{tr('report_manual_upload_title', 'UPLOAD MANUEL')} {final_status}\n\n"
            f"✅ {tr('report_success', 'Succès')} : {stats['success']}\n"
            f"❌ {tr('report_failures', 'Échecs')} : {stats['failed']}\n"
            f"⏭️ {tr('report_skipped', 'Simulé/Ignoré')} : {stats['skipped']}\n\n"
            f"📦 {tr('report_volume', 'Volume')} : {format_size(stats['bytes'])}\n"
            f"⚡ {tr('report_speed', 'Vitesse')} : {speed_str}\n"
            f"⏱️ {tr('report_duration', 'Durée')} : {int(duration)}s"
        )
    def get_partial_hash(self, file_path: Union[str, Path], file_size: int) -> Optional[str]:
        """Calcule un hash partiel pour identifier rapidement le fichier."""
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
        """
        Transforme la sélection utilisateur (fichiers/dossiers) en une liste plate de fichiers à uploader.
        Gère la récursivité pour les dossiers de manière robuste.
        """
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
                            if ph: local_files[rel_path] = {"full_path": str(item_path), "size": stats.st_size, "mtime": stats.st_mtime, "partial_hash": ph, "root": str(item_path)}
                    except Exception as e:
                        self.log_ui(f"{tr('log_error_read_file', 'Erreur Lecture Fichier')}: {item_path.name} - {e}", "red")
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
                                    if ph: local_files[rel_path] = {"full_path": str(full_path), "size": stats.st_size, "mtime": stats.st_mtime, "partial_hash": ph, "root": str(item_path)}
                                except Exception:
                                    continue
                    except OSError as e:
                        self.log_ui(f"{tr('log_error_read_folder', 'Impossible de lire le dossier complet (Restriction OS)')}: {root_name}", "red")
            except Exception as main_e:
                self.log_ui(f"{tr('log_error_global_path', 'Erreur chemin global')}: {main_e}", "red")
        return local_files
                                                                                   
                                                
