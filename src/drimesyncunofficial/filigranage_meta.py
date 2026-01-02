import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD, LEFT
from drimesyncunofficial.constants import COL_BLEU2, COL_TEXT_GRIS, COL_VERT, COL_ROUGE, ANDROID_DOWNLOAD_PATH
from drimesyncunofficial.ui_utils import create_back_button
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.filigranage_engine import OmegaEngine
import os
from drimesyncunofficial.i18n import tr

class MetadataReaderManager:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.main_box = None
        self.results_label = None

    def show(self):
        self.main_box = toga.Box(style=Pack(direction=COLUMN))
        
        nav_box = toga.Box(style=Pack(direction=ROW, margin=10, align_items=CENTER))
        btn_back = create_back_button(self.app.retour_arriere, margin_bottom=0)
        nav_box.add(btn_back)
        nav_box.add(toga.Box(style=Pack(flex=1)))
        self.main_box.add(nav_box)

        header = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15, margin_left=20))
        header.add(toga.Label(tr("meta_title", "--- LECTURE MÉTADONNÉES ---"), style=Pack(font_size=12, font_weight=BOLD, color=COL_BLEU2, text_align=LEFT, margin_bottom=2)))
        header.add(toga.Label(tr("meta_subtitle", "Vérification Forensique"), style=Pack(font_size=10, color=COL_TEXT_GRIS, text_align=LEFT, margin_bottom=5)))
        self.main_box.add(header)

        action_card = toga.Box(style=Pack(direction=COLUMN, margin=10, padding=10))
        
        lbl_info = toga.Label(
            tr("meta_info_label", "Sélectionnez un fichier sécurisé (.pdf, .png, .jpg...)\npour analyser ses métadonnées, filigranes et signatures."),
            style=Pack(margin_bottom=15, font_size=11, color=COL_TEXT_GRIS)
        )
        action_card.add(lbl_info)

        btn_scan = toga.Button(
            tr("btn_select_file", "📂 SÉLECTIONNER UN FICHIER"), 
            on_press=self.action_select_file,
            style=Pack(background_color=COL_BLEU2, color='white', font_weight=BOLD, font_size=12, height=45)
        )
        action_card.add(btn_scan)
        self.main_box.add(action_card)

        res_container = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))
        res_container.add(toga.Label(tr("meta_res_title", "Résultats d'analyse :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        self.results_box = toga.Box(style=Pack(direction=COLUMN))
        self.results_label = toga.Label(tr("meta_no_file", "Aucun fichier analysé."), style=Pack(font_size=10, color=COL_TEXT_GRIS))
        self.results_box.add(self.results_label)
        
        scroll = toga.ScrollContainer(content=self.results_box, style=Pack(flex=1))
        res_container.add(scroll)
        
        self.main_box.add(res_container)

        self.app.changer_ecran(self.main_box)

    def action_select_file(self, widget):
        valid_exts = ['.pdf', '.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.tiff', '.tif']
        ftypes_desktop = ["pdf", "jpg", "jpeg", "png", "heic", "webp", "bmp", "tiff", "tif"]

        if self.app.is_mobile:
            browser = AndroidFileBrowser(
                self.app, 
                self.on_file_picked, 
                initial_path=ANDROID_DOWNLOAD_PATH, 
                folder_selection_mode=False,
                valid_extensions=valid_exts
            )
            self.app.main_window.content = browser
        else:
            async def _ask_desktop():
                fname = await self.app.main_window.dialog(toga.OpenFileDialog(
                    title="Sélectionner un fichier", 
                    multiple_select=False, 
                    file_types=ftypes_desktop
                ))
                if fname:
                    self.on_file_picked([fname])
            self.app.loop.create_task(_ask_desktop())

    def on_file_picked(self, paths):
        self.app.main_window.content = self.main_box
        
        if not paths:
            self.results_label.text = "Sélection annulée."
            return

        file_path = str(paths[0])
        safe_name = os.path.basename(file_path)
        
        while self.results_box.children:
            self.results_box.remove(self.results_box.children[0])

        self.results_label = toga.Label(f"Lecture en cours : {safe_name}...", style=Pack(font_size=10, color=COL_BLEU2))
        self.results_box.add(self.results_label)
        
        def _read_and_update():
            try:
                engine = OmegaEngine()
                meta = engine.read_metadata(file_path)
                
                def _update_ui(metadata):
                    while self.results_box.children:
                         self.results_box.remove(self.results_box.children[0])

                    if not metadata:
                        self.results_box.add(toga.Label("Aucune métadonnée trouvée.", style=Pack(font_size=10)))
                        return
                    
                    for k, v in metadata.items():
                        val_str = str(v)
                        if len(val_str) > 200: val_str = val_str[:200] + "..."
                        
                        row = toga.Box(style=Pack(direction=ROW, margin_bottom=3))
                        row.add(toga.Label(f"{k}:", style=Pack(font_weight=BOLD, width=120, font_size=9, color=COL_BLEU2)))
                        row.add(toga.Label(val_str, style=Pack(font_size=9, flex=1)))
                        self.results_box.add(row)

                self.app.loop.call_soon_threadsafe(_update_ui, meta)
            except Exception as e:
                def _show_err(err):
                    self.results_box.add(toga.Label(f"Erreur : {err}", style=Pack(color=COL_ROUGE, font_size=10)))
                self.app.loop.call_soon_threadsafe(_show_err, str(e))

        import threading
        threading.Thread(target=_read_and_update, daemon=True).start()
