import toga
import os
import asyncio
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from drimesyncunofficial.constants import COL_BLEU, COL_ROUGE, ANDROID_DOWNLOAD_PATH
from drimesyncunofficial.utils import format_size
class AndroidFileBrowser(toga.Box):
    """
    Un explorateur de fichiers simple fait avec des widgets Toga.
    Remplace les dialogues natifs manquants sur Android.
    Modes : 
      - 'folder' : Le bouton 'Choisir ce dossier' valide la sélection.
      - 'file' : Cliquer sur un fichier le sélectionne (mode par défaut).
    """
    def __init__(self, app, on_select_callback, initial_path=ANDROID_DOWNLOAD_PATH, valid_extensions=None, folder_selection_mode=False):
        super().__init__(style=Pack(direction=COLUMN, flex=1, background_color="white"))
        self.app = app
        self.on_select_callback = on_select_callback
        self.current_path = initial_path
        self.valid_extensions = [ext.lower() for ext in valid_extensions] if valid_extensions else None
        self.folder_selection_mode = folder_selection_mode
        header = toga.Box(style=Pack(direction=ROW, padding=5, background_color="#eee"))
        self.lbl_path = toga.Label(self.current_path, style=Pack(padding=5, flex=1, font_weight='bold'))
        header.add(self.lbl_path)
        self.add(header)
        toolbar = toga.Box(style=Pack(direction=ROW, padding=5))
        toolbar.add(toga.Button("⬆️ Remonter", on_press=self.go_up, style=Pack(padding=2, flex=1)))
        if self.folder_selection_mode:
            toolbar.add(toga.Button("✅ Choisir ce dossier", on_press=self.select_current_folder, style=Pack(padding=2, flex=1, background_color=COL_BLEU, color="white")))
        toolbar.add(toga.Button("❌ Annuler", on_press=self.do_cancel, style=Pack(padding=2, flex=1, background_color=COL_ROUGE, color="white")))
        self.add(toolbar)
        self.file_list = toga.DetailedList(
            data=[],
            on_select=self.on_row_select,
            style=Pack(flex=1)
        )
        self.add(self.file_list)
        self.refresh_list()
    def refresh_list(self):
        display_path = os.path.basename(self.current_path)
        if not display_path: display_path = self.current_path
        
        items = []
        try:
            from pathlib import Path
            p = Path(self.current_path)
            
            for entry in p.iterdir():
                try:
                    name = entry.name
                    if name.startswith('.'): continue
                    
                    is_dir = entry.is_dir()
                    
                    if not is_dir and self.valid_extensions and not self.folder_selection_mode:
                         if not any(name.lower().endswith(ext) for ext in self.valid_extensions):
                             continue

                    display_name = name
                    if len(name) > 35:
                        display_name = name[:15] + "..." + name[-15:]
                            
                    prefix = "📁 " if is_dir else "📄 "
                    
                    try:
                        size_str = "Dossier" if is_dir else format_size(entry.stat().st_size)
                    except:
                        size_str = "?"
                        
                    items.append({
                        "icon": None, 
                        "title": prefix + display_name,
                        "subtitle": size_str,
                        "is_dir": is_dir,
                        "path": str(entry)
                    })
                except Exception:
                    continue
                    
        except PermissionError:
            async def show_error():
                await self.app.main_window.dialog(toga.InfoDialog("Accès Refusé", "Android bloque l'accès à ce dossier.\nEssayez le dossier 'Download'."))
            asyncio.ensure_future(show_error())
            self.go_up(None)
            return
        except Exception as e:
            items.append({"title": f"⚠️ Erreur globale: {e}", "subtitle": "", "icon": None, "path": None})
            
        self.lbl_path.text = f"📂 {display_path} ({len(items)} éléments)"
            
        items.sort(key=lambda x: (not x.get('is_dir', False), x.get('title', "").lower()))
        self.file_list.data = items
    def on_row_select(self, widget, row=None):
        if row is None: row = widget.selection
        if not row: return
        try: is_dir = row.is_dir
        except: is_dir = getattr(row, 'is_dir', False)
        try: path = row.path
        except: path = getattr(row, 'path', None)
        if not path: return
        if is_dir:
            self.current_path = path
            self.refresh_list()
        else:
            if not self.folder_selection_mode:
                self.on_select_callback([path])
    def select_current_folder(self, widget):
        if self.folder_selection_mode:
            self.on_select_callback(self.current_path)
    def go_up(self, widget):
        parent = os.path.dirname(self.current_path)
        if parent and len(parent) > 1: 
            self.current_path = parent
            self.refresh_list()
    def do_cancel(self, widget):
        self.on_select_callback(None)