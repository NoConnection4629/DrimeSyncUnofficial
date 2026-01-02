import toga
import asyncio
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import COL_VERT, COL_ROUGE, COL_GRIS, COL_TEXT_GRIS, COL_JAUNE, COL_BLEU, CONF_KEY_API_KEY
from drimesyncunofficial.utils import format_size, format_display_date, truncate_path_smart
from drimesyncunofficial.ui_utils import create_back_button
from typing import Any, Optional, List, Dict
from drimesyncunofficial.i18n import tr
class TrashManager:
    """
    Gestionnaire de la Corbeille.
    Permet de visualiser, restaurer ou supprimer définitivement les fichiers supprimés.
    """
    def __init__(self, app: Any):
        self.app = app
        self.window: Optional[toga.Window] = None
        self.trash_files_cache: List[Dict[str, Any]] = []
    def show(self) -> None:
        """Affiche l'interface de gestion de la corbeille."""
        if not self.app.config_data.get(CONF_KEY_API_KEY):
            self.app.loop.create_task(self.app.main_window.dialog(toga.InfoDialog("Erreur", "Veuillez configurer la clé API.")))
            return
        main_box = toga.Box(style=Pack(direction=COLUMN, flex=1))

        top_box = toga.Box(style=Pack(direction=COLUMN, margin=5))
        top_box.add(create_back_button(self.app.retour_arriere))
        top_box.add(toga.Label(tr("trash_title", "--- CORBEILLE ---"), style=Pack(font_weight=BOLD, color=COL_ROUGE, margin_bottom=10, font_size=12)))
        top_box.add(toga.Label(tr("expl_choose_ws", "Choisir le Workspace :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        items = ["Espace Personnel (ID: 0)"]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache: 
                items.append(f"{ws['name']} (ID: {ws['id']})")
        self.selection_ws = toga.Selection(items=items, style=Pack(margin_bottom=15))
        if items: self.selection_ws.value = items[0]
        self.selection_ws.on_change = self.refresh
        top_box.add(self.selection_ws)

        actions_group = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        
        actions_group.add(toga.Button(tr("trash_refresh_btn", "🔄 Actualiser la liste"), on_press=self.refresh, style=Pack(margin_bottom=5)))

        row_ops = toga.Box(style=Pack(direction=ROW))
        row_ops.add(toga.Button(tr("trash_restore", "Restaurer"), on_press=self.action_restore, style=Pack(flex=1, margin_right=5, background_color=COL_VERT, color='white')))
        row_ops.add(toga.Button(tr("trash_destroy", "Détruire"), on_press=self.action_delete_selected, style=Pack(flex=1, margin_right=5, background_color=COL_ROUGE, color='white')))
        row_ops.add(toga.Button(tr("trash_empty", "VIDER"), on_press=self.action_empty_trash_only, style=Pack(flex=0.8, background_color='#ff9f43', color='white', font_weight=BOLD)))
        actions_group.add(row_ops)
        
        top_box.add(actions_group)
        top_box.add(toga.Label("Éléments supprimés :", style=Pack(font_weight=BOLD, margin_bottom=5)))
        main_box.add(top_box)

        middle_box = toga.Box(style=Pack(flex=1, margin=5))
        if self.app.is_mobile:
            self.list = toga.DetailedList(style=Pack(flex=1))
            middle_box.add(self.list)
        else:
            self.table = toga.Table(
                headings=[tr("dl_col_name", "Nom"), tr("dl_col_size", "Taille"), tr("dl_col_type", "Type"), 'Supprimé le'], 
                accessors=['name', 'size', 'type', 'deleted_at'],
                multiple_select=True, 
                style=Pack(flex=1),
            )
            middle_box.add(self.table)
        main_box.add(middle_box)

        bottom_box = toga.Box(style=Pack(direction=COLUMN, margin=5, margin_bottom=10))
        self.status = toga.Label("Prêt.", style=Pack(margin_top=5, font_weight=BOLD, font_size=9, color='gray'))
        bottom_box.add(self.status)
        main_box.add(bottom_box)

        self.app.changer_ecran(main_box)
        self.refresh(None)
    def _get_ws_id(self) -> str:
        val = self.selection_ws.value
        if not val or "ID: 0" in val: return "0"
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return "0"
    def _find_file_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrouve un fichier dans le cache par son nom (ignorer l'emoji)."""
        clean_search_name = name.replace("📁 ", "").replace("📄 ", "")
        for f in self.trash_files_cache:
            if str(f.get('name') or "Sans nom") == clean_search_name:
                return f
        return None
    async def load_data(self) -> None:
        """Charge la liste des fichiers supprimés depuis l'API."""
        target_ws_id = self._get_ws_id()
        loop = asyncio.get_running_loop()
        total_size_bytes = 0
        try:
            self.status.text = "Chargement en cours..."
            def do(): 
                try: return self.app.api_client.list_files({"workspaceId": target_ws_id, "deletedOnly": 1})
                except Exception: return None
            data = await loop.run_in_executor(None, do)
            if not data or isinstance(data, dict) and data.get('status_code', 0) >= 400 or "data" not in data: 
                self.status.text = "Aucune donnée."
                self.trash_files_cache = []
                if self.app.is_mobile: self.list.data = []
                else: self.table.data = []
                return
            files = data.get("data", [])
            self.trash_files_cache = files
            if self.app.is_mobile:
                list_data = []
                for f in files:
                    size_value = f.get('file_size') or f.get('size') or 0
                    try: total_size_bytes += int(size_value)
                    except ValueError: pass
                    size_display = format_size(size_value)
                    is_folder = str(f.get('type')) == 'folder'
                    icon_emoji = "📁 " if is_folder else "📄 "
                    display_name = str(f.get('name') or "Sans nom")
                    final_display_name = truncate_path_smart(display_name, max_length=25)
                    list_data.append({
                        "icon": None, 
                        "title": icon_emoji + final_display_name, 
                        "subtitle": size_display,
                        "id": str(f.get('id'))
                    })
                self.list.data = list_data
            else:
                table_data = []
                for f in files:
                    size_value = f.get('file_size') or f.get('size') or 0
                    try: total_size_bytes += int(size_value)
                    except ValueError: pass
                    size_display = str(format_size(size_value))
                    ftype_raw = str(f.get('type', 'file')).upper()
                    display_type = "DOSSIER" if ftype_raw == 'FOLDER' else str(f.get('extension') or "file")
                    
                    is_folder = (ftype_raw == 'FOLDER')
                    icon_emoji = "📁 " if is_folder else "📄 "
                    display_name = str(f.get('name') or "Sans nom")
                    
                    table_data.append({
                        "name": icon_emoji + display_name, 
                        "size": size_display,
                        "type": display_type,
                        "deleted_at": str(format_display_date(f.get('deleted_at'))),
                        "file_id": str(f.get('id'))
                    })
                self.table.data = table_data
            total_display = format_size(total_size_bytes)
            self.status.text = f"{len(files)} éléments | {tr('dl_col_size', 'Taille')} totale: {total_display}"
        except Exception as e:
            self.status.text = f"Erreur: {e}"
    def refresh(self, widget: Any) -> None: 
        asyncio.create_task(self.load_data())
    def get_selection(self) -> List[Dict[str, Any]]:
        """Récupère les éléments sélectionnés dans la liste/tableau."""
        selection_rows = []
        if self.app.is_mobile: 
            if self.list.selection: selection_rows = [self.list.selection]
        else:
            if self.table.selection: selection_rows = self.table.selection
        if not selection_rows: return []
        selected_files = []
        for row in selection_rows:
            try:
                rid = None
                if hasattr(row, 'file_id'): rid = str(row.file_id)
                elif hasattr(row, 'id'): rid = str(row.id)
                
                if rid:
                                             
                    found = next((f for f in self.trash_files_cache if str(f['id']) == rid), None)
                    if found: selected_files.append(found)
                else:
                                                               
                    target_name = row.title if hasattr(row, 'title') else row.name
                    found = self._find_file_by_name(target_name)
                    if found: selected_files.append(found)
            except: pass
        return selected_files
    async def action_restore(self, widget: Any) -> None:
        """Restaure les fichiers sélectionnés."""
        files = self.get_selection()
        if not files: 
            await self.app.main_window.dialog(toga.InfoDialog("Info", tr("dl_msg_select_items", "Aucun fichier sélectionné.")))
            return
        self.status.text = f"Restauration de {len(files)} fichiers en cours..."
        ids = [str(f['id']) for f in files]
        success = await self._batch_restore_async(ids)
        await self.load_data() 
        if success:
            await self.app.main_window.dialog(toga.InfoDialog(tr("title_success", "Succès"), tr("trash_success_restore", "{count} élément(s) restauré(s).").format(count=len(files))))
        else:
            await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "La restauration a échoué."))
    async def _batch_restore_async(self, ids: List[str]) -> bool:
        loop = asyncio.get_running_loop()
        all_success = True
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            def do():
                try: return self.app.api_client.restore_entry(batch)
                except Exception: return None
            res = await loop.run_in_executor(None, do)
            if not res:
                all_success = False
                print(f"ÉCHEC RESTAURATION BATCH. Réponse: {res}")
        return all_success
    async def action_delete_selected(self, widget: Any) -> None:
        """Supprime définitivement les fichiers sélectionnés."""
        files = self.get_selection()
        if not files:
            await self.app.main_window.dialog(toga.InfoDialog("Info", tr("dl_msg_select_items", "Aucun fichier sélectionné.")))
            return
        confirm = await self.app.main_window.dialog(toga.QuestionDialog("CONFIRMATION", tr("trash_confirm_delete", "Êtes-vous sûr ?").format(count=len(files))))
        if not confirm: return
        ids = [str(f['id']) for f in files]
        await self._batch_delete_async(ids, delete_forever=True)
        await self.load_data()
        await self.app.main_window.dialog(toga.InfoDialog("Terminé", tr("trash_success_delete", "{count} élément(s) détruit(s) définitivement.").format(count=len(files))))
    async def action_empty_trash_only(self, widget: Any) -> None:
        """Vide l'intégralité de la corbeille du workspace sélectionné."""
        if not self.trash_files_cache:
            await self.app.main_window.dialog(toga.InfoDialog("Info", tr("expl_empty", "La corbeille est déjà vide.")))
            return
        confirm = await self.app.main_window.dialog(toga.QuestionDialog("VIDER TOUT", tr("trash_confirm_empty", "Voulez-vous vraiment VIDER TOUT ({count}) ?").format(count=len(self.trash_files_cache))))
        if not confirm: return
        ids = [str(f['id']) for f in self.trash_files_cache]
        await self._batch_delete_async(ids, delete_forever=True)
        await self.load_data()
        await self.app.main_window.dialog(toga.InfoDialog("Terminé", "Corbeille vidée avec succès."))
    async def _batch_delete_async(self, ids: List[str], delete_forever: bool) -> None:
        """Fonction utilitaire pour supprimer des fichiers par lots."""
        loop = asyncio.get_running_loop()
        self.status.text = f"Suppression en cours ({len(ids)} éléments)..."
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            def do(): 
                try: return self.app.api_client.delete_entries(batch, delete_forever=delete_forever)
                except Exception: return None
            await loop.run_in_executor(None, do)