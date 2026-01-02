import toga
import asyncio
import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import COL_BLEU, COL_VERT, COL_JAUNE, COL_ROUGE, COL_TEXT_GRIS
from drimesyncunofficial.base_transfer_manager import BaseTransferManager
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.utils import format_size, truncate_path_smart, ensure_long_path_aware
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.ui_thread_utils import run_in_background
from drimesyncunofficial.i18n import tr

class BaseDownloadManager(BaseTransferManager):
    """
    Gestionnaire de base pour les téléchargements (Manuel & Workspace).
    Gère:
    - Sélection de Workspace
    - Navigation (Dossier Parent / Ouvrir)
    - Listing des fichiers (UI Table/List)
    - File d'attente de téléchargement via worker
    """
    def __init__(self, app: Any):
        super().__init__(app)
        self.files_cache: List[Dict[str, Any]] = []
        self.current_folder_id: Optional[str] = None
        self.history: List[Optional[str]] = []
        self.DOWNLOAD_CHUNK_SIZE: int = 32768
        
        self.sel_ws: Optional[toga.Selection] = None
        self.list: Optional[toga.DetailedList] = None   
        self.table: Optional[toga.Table] = None
        self.lbl_status: Optional[toga.Label] = None
        
        self.btn_up: Optional[toga.Button] = None
        self.btn_open: Optional[toga.Button] = None
        
        self.main_box: Optional[toga.Box] = None
        self.main_box_content = None

    def show(self) -> None:
        """Affiche l'interface. À surcharger pour ajouter des éléments spécifiques si besoin."""
        self._init_ui()

    def _init_ui(self, title: str = "DOWNLOAD", title_color: str = COL_BLEU) -> None:
        """Initialisation standard de l'UI."""
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=20, flex=1))
        
        box.add(create_back_button(self.go_back))
        box.add(toga.Label(title, style=Pack(font_weight=BOLD, color=title_color, margin_bottom=5, font_size=12)))
        
        box.add(toga.Label(tr("lbl_workspace", "Workspace :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        items = ["Espace Personnel (ID: 0)"]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: items.append(f"{ws['name']} (ID: {ws['id']})")
        
        self.sel_ws = toga.Selection(items=items, style=Pack(margin_bottom=10), on_change=self.refresh_content)
        box.add(self.sel_ws)
        
        box_list_header = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items='center'))
        box_list_header.add(toga.Label(tr("lbl_remote_content", "Contenu distant :"), style=Pack(font_weight=BOLD, width=120)))
        
        self.btn_up = toga.Button(tr("btn_parent_folder", "⬆ Dossier Parent"), on_press=self.action_up, style=Pack(flex=1, margin_right=5))
        box_list_header.add(self.btn_up)
        
        self.btn_open = toga.Button(tr("btn_open", "📂 Ouvrir"), on_press=self.action_open, style=Pack(flex=1))
        box_list_header.add(self.btn_open)
        
        box.add(box_list_header)
        
        if self.app.is_mobile:
            self.list = toga.DetailedList(on_select=self.on_item_select, style=Pack(flex=1, height=300, margin_bottom=10))
            box.add(self.list)
        else:
            self.table = toga.Table(
                headings=[tr("dl_col_name", "Nom"), tr("dl_col_size", "Taille"), tr("dl_col_type", "Type")], 
                accessors=['name', 'size', 'type'],
                multiple_select=True, 
                on_activate=self.on_table_activate,
                style=Pack(flex=1, margin_bottom=10)
            )
            box.add(self.table)
            
        self.lbl_status = toga.Label(tr("dl_status_ready", "Prêt."), style=Pack(color='gray', font_size=9, margin_bottom=5))
        box.add(self.lbl_status)
        
        self.box_actions_container = toga.Box(style=Pack(direction=COLUMN))
        self.btn_action_main = toga.Button(tr("btn_dl_selection", "⬇️ TÉLÉCHARGER SÉLECTION"), on_press=self.action_download_main, 
                                               style=Pack(flex=1, background_color=title_color, color='white', height=50, font_weight=BOLD))
        
        self.box_controls = toga.Box(style=Pack(direction=ROW, visibility='hidden', height=0, flex=1))
        self.btn_pause = toga.Button(tr("btn_pause", "⏸️ Pause"), on_press=self.action_toggle_pause, style=Pack(flex=1, margin_right=5, background_color=COL_JAUNE, color='white', height=50, font_weight=BOLD, visibility='hidden'))
        self.btn_cancel = toga.Button(tr("btn_cancel_stop", "⏹️ Annuler"), on_press=self.action_cancel, style=Pack(flex=1, margin_left=5, background_color=COL_ROUGE, color='white', height=50, font_weight=BOLD, visibility='hidden'))
        self.box_controls.add(self.btn_pause)
        self.box_controls.add(self.btn_cancel)
        
        self.box_actions_container.add(self.btn_action_main)
        self.box_actions_container.add(self.box_controls)
        box.add(self.box_actions_container)
        
        self.lbl_progress = toga.Label("", style=Pack(font_weight=BOLD, margin_top=5, font_size=10, color=COL_JAUNE))
        box.add(self.lbl_progress)
        
        box.add(toga.Label(tr("lbl_log", "Log :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        self.txt_logs = create_logs_box(font_size=8, color=COL_TEXT_GRIS, height=150)
        box.add(self.txt_logs)
        
        main_container.content = box
        self.main_box = box
        self.main_box_content = main_container
        
        self.app.changer_ecran(main_container)
        self._set_ui_running(False)
        self.refresh_content(None)

    def go_back(self, widget):
        if self.is_running:
            self.action_cancel(None)
        self.app.retour_arriere(widget)

    def _get_ws_id(self) -> str:
        if not self.sel_ws: return "0"
        val = self.sel_ws.value
        if not val: return "0"
        if "ID: 0" in val: return "0"
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return "0"

    def refresh_content(self, widget):
        self.current_folder_id = None
        self.history = []
        asyncio.create_task(self.load_content())

    async def load_content(self):
        ws_id = self._get_ws_id()
        folder_id = self.current_folder_id if self.current_folder_id else 0
        self.lbl_status.text = "Chargement..."
        loop = asyncio.get_running_loop()
        
        try:
            def do(): 
                return self.app.api_client.list_files(params={"folderId": folder_id, "workspaceId": ws_id, "deletedOnly": 0})
            
            data = await loop.run_in_executor(None, do)
            
            if not data:
                self.files_cache = []
                self._update_list_data([])
                self.lbl_status.text = "Erreur chargement."
                return

            self.files_cache = data.get("data", [])
            self._display_files(self.files_cache)
            self.lbl_status.text = f"{len(self.files_cache)} éléments."
            
        except Exception as e:
            self.lbl_status.text = f"Erreur: {e}"

    def _display_files(self, files: List[Dict[str, Any]]):
        """Prepare et affiche les données dans la liste/table."""
        if self.app.is_mobile:
            new_data = []
            for f in files:
                processed = self._process_file_item(f)
                size_val = format_size(f.get('file_size') or f.get('size') or 0)
                is_folder = str(f.get('type')) == 'folder'
                icon_emoji = "📁 " if is_folder else "📄 "
                
                display_name = processed.get('name', str(f.get('name')))
                final_display_name = truncate_path_smart(display_name)
                
                new_data.append({
                    "icon": None, 
                    "title": icon_emoji + final_display_name, 
                    "subtitle": size_val,
                    "id_item": str(f.get('id')),
                    "type_item": str(f.get('type'))
                })
            self.list.data = new_data
        else:
            new_data = []
            for f in files:
                processed = self._process_file_item(f)
                size_val = str(format_size(f.get('file_size') or f.get('size') or 0))
                ftype = "Dossier" if str(f.get('type')) == 'folder' else "Fichier"
                display_name = processed.get('name', str(f.get('name')))
                
                new_data.append((display_name, size_val, ftype))
            self.table.data = new_data

    def _process_file_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Hook pour modifier l'item avant affichage (ex: déchiffrement du nom)"""
        return item

    def on_item_select(self, widget):
        pass

    def on_table_activate(self, widget, row):
        target_name = row.name 
        for f in self.files_cache:
            processed = self._process_file_item(f)
            if processed.get('name') == target_name and str(f.get('type')) == 'folder':
                self._enter_folder(str(f.get('id')))
                return

    def _enter_folder(self, folder_id: str):
        self.history.append(self.current_folder_id)
        self.current_folder_id = folder_id
        asyncio.create_task(self.load_content())

    def action_up(self, widget):
        if not self.history: return
        self.current_folder_id = self.history.pop()
        asyncio.create_task(self.load_content())

    def action_open(self, widget):
        selection = []
        if self.app.is_mobile:
            if self.list.selection: selection = [self.list.selection]
        else:
            if self.table.selection: selection = self.table.selection
        if not selection: return
        
        
        first_sel = selection[0]
        
        if self.app.is_mobile:
            item_id = getattr(first_sel, 'id_item', None)
            item_type = getattr(first_sel, 'type_item', None)
            if item_type == 'folder' and item_id:
                self._enter_folder(item_id)
        else:
            target_name = first_sel.name
            for f in self.files_cache:
                processed = self._process_file_item(f)
                if processed.get('name') == target_name and str(f.get('type')) == 'folder':
                    self._enter_folder(str(f.get('id')))
                    return

    def action_download_main(self, widget):
        """Action principale de téléchargement (Sélection ou Tout)."""
        if self.app.is_mobile:
            def on_folder_picked(result_path):
                self.app.main_window.content = self.main_box_content
                if result_path:
                    asyncio.create_task(self.start_download(str(result_path)))
                else:
                    self.log_ui("Sélection annulée.", "yellow")
            
            from drimesyncunofficial.constants import ANDROID_DOWNLOAD_PATH
            browser = AndroidFileBrowser(self.app, on_folder_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
            self.app.main_window.content = browser
        else:
            asyncio.create_task(self.start_download())

    async def start_download(self, target_folder: Optional[str] = None, selection: List[Dict[str, Any]] = None):
        """Collecte les tâches et lance le worker."""
        if not selection and self.app.is_mobile:
            pass

        if not selection:
            selection = []
            if self.app.is_mobile:
                 if self.list.selection:
                     row = self.list.selection
                     if hasattr(row, 'id_item'):
                         for f in self.files_cache:
                             if str(f['id']) == str(row.id_item):
                                 selection.append(f)
                                 break
            else:
                if self.table.selection:
                    for row in self.table.selection:
                        try:
                             idx = self.table.data.index(row)
                             if idx < len(self.files_cache):
                                 selection.append(self.files_cache[idx])
                        except: pass
        
        if not selection:
            await self.app.main_window.dialog(toga.InfoDialog(tr("title_info", "Info"), tr("dl_msg_select_items", "Sélectionnez des éléments.")))
            return

        if not target_folder:
            if not self.app.is_mobile:
                path = await self.app.main_window.dialog(toga.SelectFolderDialog("Dossier de destination"))
                if not path: return
                target_folder = str(path)
            else:
                from drimesyncunofficial.constants import ANDROID_DOWNLOAD_PATH
                target_folder = ANDROID_DOWNLOAD_PATH

        self.download_target_folder = target_folder
        self.is_running = True
        self.is_paused = False
        self.is_cancelled = False
        self.processed_files_count = 0
        self.total_downloaded_bytes = 0
        
        self._set_ui_running(True)
        self.stop_event.clear()
        self.progress_lock = threading.Lock()
        
        self.lbl_status.text = "Préparation..."
        self.log_ui(f"Cible : {target_folder}", "green")
        
        run_in_background(self._spinner_loop)
        
        tasks = []
        ws_id = self._get_ws_id()
        
        for item in selection:
            processed = self._process_file_item(item)
            i_name = processed.get('name', item.get('name'))
            i_id = str(item.get('id'))
            i_type = str(item.get('type'))
            i_size = int(item.get('file_size') or item.get('size') or 0)
            
            if i_type == 'folder':
                await self.collect_tasks_recursive(i_id, i_name, self.download_target_folder, ws_id, tasks)
            else:
                target_path = Path(self.download_target_folder) / i_name
                
                i_hash = item.get('hash')
                if not i_hash:
                     i_hash = await self._fetch_file_hash(i_id)
                
                self.log_debug(f"Task: {i_name}")
                if i_hash:
                    tasks.append({
                        "url": f"{self.app.api_client.api_base_url}/file-entries/download/{i_hash}",
                        "path": str(target_path),
                        "name": i_name, "size": i_size
                    })
        
        if not tasks:
            self._set_ui_running(False)
            self.lbl_status.text = "Rien à télécharger."
            return

        self.total_files_count = len(tasks)
        self.total_size = sum(t['size'] for t in tasks)
        
        try: nb_workers = int(self.app.config_data.get('workers', 5))
        except: nb_workers = 5
        self.semaphore = asyncio.Semaphore(nb_workers)
        
        msg_start = f"Démarrage ({len(tasks)} fichiers)..."
        self.lbl_status.text = msg_start
        self.log_ui(msg_start, "green")
        
        loop = asyncio.get_running_loop()
        tasks_coroutines = [self._download_worker_bounded(t) for t in tasks]
        results = await asyncio.gather(*tasks_coroutines)
        
        success = sum(1 for r in results if r and r.get('status') == 'success')
        failed = len(tasks) - success
        
        self._set_ui_running(False)
        
        self._finalize_renaming(self.download_target_folder)
        
        final_msg = f"Terminé.\nSuccès: {success}\nEchecs: {failed}"
        self.stop_event.set()
        self.update_status_ui(tr("transfer_status_done", "Terminé."), COL_VERT)
        await self.app.main_window.dialog(toga.InfoDialog(tr("title_report", "Rapport"), final_msg))

    async def _fetch_file_hash(self, entry_id: str) -> Optional[str]:
        """Helper to get hash if missing."""
        loop = asyncio.get_running_loop()
        def do(): return self.app.api_client.get_file_entry(entry_id)
        try:
            res = await loop.run_in_executor(None, do)
            if res and res.status_code == 200:
                data = res.json()
                if data.get('hash'): return data['hash']
                if data.get('fileEntry', {}).get('hash'): return data['fileEntry']['hash']
        except: pass
        return None

    async def collect_tasks_recursive(self, folder_id, folder_name, parent_path, ws_id, task_list):
        if self.is_cancelled: return
        
        raw_path = Path(parent_path) / folder_name
        long_path_str = ensure_long_path_aware(str(raw_path))
        local_folder_path = Path(long_path_str)
        
        if not local_folder_path.exists():
            local_folder_path.mkdir(parents=True, exist_ok=True)
            await asyncio.sleep(0.01)
            
        loop = asyncio.get_running_loop()
        def do_list(): return self.app.api_client.list_files(params={"folderId": folder_id, "workspaceId": ws_id, "deletedOnly": 0})
        
        try:
            data = await loop.run_in_executor(None, do_list)
        except: return
        
        if not data: return
        children = data.get("data", [])
        
        for child in children:
            if self.is_cancelled: return
            processed = self._process_file_item(child)
            c_name = processed.get('name', child.get('name'))
            c_id = str(child.get('id'))
            c_type = str(child.get('type'))
            c_size = int(child.get('file_size') or child.get('size') or 0)
            
            if c_type == 'folder':
                await self.collect_tasks_recursive(c_id, c_name, str(local_folder_path), ws_id, task_list)
            else:
                target_path = local_folder_path / c_name
                c_hash = child.get('hash')
                if not c_hash: c_hash = await self._fetch_file_hash(c_id)
                
                if c_hash:
                    task_list.append({
                        "url": f"{self.app.api_client.api_base_url}/file-entries/download/{c_hash}",
                        "path": str(target_path),
                        "name": c_name, "size": c_size
                    })

    async def _download_worker_bounded(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        if self.is_cancelled: return {'status': 'cancelled'}
        
        async with self.semaphore:
            loop = asyncio.get_running_loop()
            success, msg, bytes_dl = await loop.run_in_executor(
                None, 
                self._download_file_worker,
                file_info['url'], file_info['path'], file_info['name'], file_info['size']
            )
            
            if success:
                self.processed_files_count += 1
                self.log_ui(f"OK: {file_info['name']}", COL_VERT)
                return {'status': 'success', 'bytes': bytes_dl}
            else:
                self.log_ui(f"Échec {file_info['name']}: {msg}", COL_ROUGE)
                return {'status': 'failed', 'error': msg}

    def _download_file_worker(self, url: str, save_path: str, file_name: str, total_size: int) -> tuple[bool, str, int]:
        """Standard download logic. Override for E2EE."""
        save_path = ensure_long_path_aware(save_path)
        
        last_error = "Unknown"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with self.app.api_client.get_download_stream(url) as r:
                    if r.status_code != 200:
                        last_error = f"HTTP {r.status_code}"
                        if r.status_code in [403, 429] and attempt < max_retries - 1:
                            time.sleep(1 + attempt)
                            continue
                        return False, last_error, 0
                    
                    with open(save_path, 'wb') as f:
                        downloaded_this = 0
                        for chunk in r.iter_content(chunk_size=self.DOWNLOAD_CHUNK_SIZE):
                            if self.is_cancelled: 
                                f.close()
                                try: Path(save_path).unlink()
                                except: pass
                                return False, "Annulé", 0
                            
                            while self.is_paused: time.sleep(0.5)
                            
                            if chunk:
                                f.write(chunk)
                                l = len(chunk)
                                downloaded_this += l
                                
                                if hasattr(self, 'progress_lock'):
                                    with self.progress_lock:
                                        self.total_downloaded_bytes += l
                                        pass
                                        
                return True, "OK", total_size
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                     time.sleep(1)
                     continue
                return False, last_error, 0
        
        return False, last_error, 0

    def _spinner_loop(self):
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        idx = 0
        while self.is_running and not self.stop_event.is_set():
            if not self.is_paused:
                txt = self.last_text
                if txt and txt[-1] in chars:
                     txt = txt[:-2].strip()

                if hasattr(self, 'total_size') and self.total_size > 0:
                     pct = (self.total_downloaded_bytes / self.total_size) * 100
                     txt = f"Téléchargement {format_size(self.total_downloaded_bytes)} / {format_size(self.total_size)} ({pct:.1f}%)"
                
                char = chars[idx % len(chars)]
                idx += 1
                
                self.update_status_ui(f"{txt} {char}", COL_BLEU)
            time.sleep(0.2)

    def _finalize_renaming(self, root_folder):
        """Restores filenames if needed (Standard functionality)."""
        from drimesyncunofficial.utils import restore_filename_from_download
        for r, d, f in os.walk(root_folder, topdown=False):
            for name in f + d:
                restored = restore_filename_from_download(name)
                if restored != name:
                    try: (Path(r)/name).rename(Path(r)/restored)
                    except: pass

