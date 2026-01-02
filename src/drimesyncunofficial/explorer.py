import toga
import asyncio
from pathlib import Path
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import COL_JAUNE, COL_ROUGE, COL_GRIS, COL_TEXT_GRIS, COL_VERT, CONF_KEY_API_KEY
from drimesyncunofficial.utils import format_size, format_display_date, truncate_path_smart
from drimesyncunofficial.utils import get_secure_secret, derive_key, generate_or_load_salt, E2EE_decrypt_name
from drimesyncunofficial.ui_utils import create_back_button
from drimesyncunofficial.i18n import tr
class ExplorerManager:
    def __init__(self, app):
        self.app = app
        self.window = None
        self.files_cache = []
        self.current_folder_id = None
        self.history = []
    def show(self):
        if not self.app.config_data.get(CONF_KEY_API_KEY):
            self.app.loop.create_task(self.app.main_window.dialog(toga.InfoDialog("Erreur", "Veuillez configurer la clé API.")))
            return
        main_box = toga.Box(style=Pack(direction=COLUMN, flex=1))

        top_box = toga.Box(style=Pack(direction=COLUMN, margin=5))
        top_box.add(create_back_button(self.app.retour_arriere))
        
        toolbar = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        toolbar.add(toga.Button(tr("expl_parent", "⬆ Parent"), on_press=self.action_up, style=Pack(flex=1, margin_right=5)))
        toolbar.add(toga.Button(tr("expl_open", "📂 Ouvrir"), on_press=self.action_open, style=Pack(flex=1, margin_right=5, background_color=COL_JAUNE, color='white')))
        toolbar.add(toga.Button(tr("btn_refresh", "🔄 Actu."), on_press=self.refresh, style=Pack(flex=1)))

        if not self.app.is_mobile:
            top_box.add(toga.Label(tr("menu_explorer", "--- EXPLORATEUR ---"), style=Pack(font_weight=BOLD, color=COL_JAUNE, margin_bottom=5, font_size=12)))
            warning_text = tr("expl_warning", "*** WARNING: ***\nRenaming or deleting files in a Mirror Workspace\nwill cause desynchronization!\nDO NOT RENAME AN ENCRYPTED FILE")
            top_box.add(toga.Label(warning_text, style=Pack(color=COL_ROUGE, font_weight=BOLD, font_size=7, margin_bottom=10, text_align='left')))
            top_box.add(toga.Label(tr("expl_choose_ws", "Choisir le Workspace :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        items = ["Espace Personnel (ID: 0)"]
        if self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache:
                items.append(f"{ws['name']} (ID: {ws['id']})")
        self.selection_ws = toga.Selection(items=items, style=Pack(flex=1))
        current_saved_ws_id = self.app.config_data.get('workspace_standard_id', '0') 
        selected_item = next((item for item in items if f"(ID: {current_saved_ws_id})" in item), items[0])
        self.selection_ws.value = selected_item
        self.selection_ws.on_change = self.refresh
        
        self.chk_show_decrypted = toga.Switch(tr("expl_decrypted_switch", "Noms déchiffrés"), style=Pack(margin_top=5))
        self.chk_show_decrypted.on_change = self.refresh

        if self.app.is_mobile:
            top_box.add(self.selection_ws)
            top_box.add(self.chk_show_decrypted)
            top_box.add(toolbar)
        else:
            top_box.add(self.selection_ws)
            top_box.add(self.chk_show_decrypted)
            top_box.add(toolbar)
        
        main_box.add(top_box)

        middle_box = toga.Box(style=Pack(flex=1, margin=5))
        
        if self.app.is_mobile:
            self.list = toga.DetailedList(on_select=self.on_mobile_select, style=Pack(flex=1))
            middle_box.add(self.list)
        else:
            self.table = toga.Table(
                headings=[tr("dl_col_name", "Nom"), tr("dl_col_size", "Taille"), tr("dl_col_type", "Type"), 'Modifié'],
                accessors=['nom', 'taille', 'type', 'modifie'],
                multiple_select=True,
                style=Pack(flex=1), 
                on_activate=self.on_table_activate
            )
            middle_box.add(self.table)
        
        main_box.add(middle_box)

        bottom_box = toga.Box(style=Pack(direction=COLUMN, margin=5, margin_bottom=30))
        
        self.status = toga.Label("Prêt.", style=Pack(margin_bottom=5, font_weight=BOLD, font_size=9, color='gray'))
        bottom_box.add(self.status)

        actions_box = toga.Box(style=Pack(direction=ROW))
        actions_box.add(toga.Button(tr("expl_rename_dialog", "Renommer"), on_press=self.action_rename, style=Pack(flex=1, margin_right=5, background_color=COL_GRIS, color='black')))
        actions_box.add(toga.Button(tr("btn_trash", "🗑️ Corbeille"), on_press=self.action_soft_delete, style=Pack(flex=1, background_color=COL_ROUGE, color='white', font_weight=BOLD)))
        bottom_box.add(actions_box)

        main_box.add(bottom_box)

        self.app.changer_ecran(main_box)
        self.refresh(None)
    def _get_ws_id(self):
        val = self.selection_ws.value
        if not val or "ID: 0" in val: return "0"
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return "0"
    def _find_file_by_name(self, name):
        clean_name = name.replace("📁 ", "").replace("📄 ", "")
        for f in self.files_cache:
            if str(f.get('name') or "Sans nom") == clean_name:
                return f
        return None
    def _get_e2ee_key(self):
        try:
            pwd = get_secure_secret('e2ee_password')
            if not pwd:
                pwd = self.app.config_data.get('e2ee_password')
            
            if not pwd: return None
            salt = generate_or_load_salt(self.app.paths)
            if not salt: return None
            return derive_key(pwd, salt)
        except: return None
    async def load_data(self):
        target_ws_id = self._get_ws_id()
        current_folder = self.current_folder_id
        loop = asyncio.get_running_loop()
        total_size_bytes = 0
        try:
            self.status.text = "Chargement..."
            params = {"deletedOnly": 0, "workspaceId": target_ws_id}
            if current_folder: params["folderId"] = current_folder
            def do(): 
                try: return self.app.api_client.list_files(params)
                except Exception: return None
            data = await loop.run_in_executor(None, do)
            if not data or "data" not in data: 
                self.status.text = "Dossier vide ou erreur."
                self.files_cache = []
                if self.app.is_mobile: self.list.data = []
                else: self.table.data = []
                return
            self.files_cache = data.get("data", [])
            count = len(self.files_cache)
            e2ee_key = None
            if self.chk_show_decrypted.value:
                e2ee_key = self._get_e2ee_key()
            if self.app.is_mobile:
                list_data = []
                for f in self.files_cache:
                    size_value = f.get('file_size') or f.get('size') or 0
                    try: total_size_bytes += int(size_value)
                    except ValueError: pass
                    size_display = format_size(size_value)
                    file_type = str(f.get('type')).upper()
                    is_folder = (file_type == 'FOLDER')
                    icon_emoji = "📁 " if is_folder else "📄 "
                    display_name = str(f.get('name') or "Sans nom")
                    if e2ee_key:
                        if display_name.endswith('.enc'):
                             decrypted = E2EE_decrypt_name(display_name[:-4], e2ee_key)
                             if decrypted != display_name[:-4]: display_name = decrypted
                        else:
                            p_name = Path(display_name)
                            base, ext = p_name.stem, p_name.suffix
                            if base:
                                decrypted_base = E2EE_decrypt_name(base, e2ee_key)
                                if decrypted_base != base: display_name = f"{decrypted_base}{ext}"
                                else:
                                    decrypted_full = E2EE_decrypt_name(display_name, e2ee_key)
                                    if decrypted_full != display_name: display_name = decrypted_full
                    
                                                               
                    final_display_name = truncate_path_smart(display_name, max_length=25)
                    
                    list_data.append({
                        "icon": None, 
                        "title": icon_emoji + final_display_name, 
                        "subtitle": size_display,
                        "id": str(f.get('id')), 
                        "type": file_type
                    })
                self.list.data = list_data
            else:
                table_data = []
                for f in self.files_cache:
                    size_value = f.get('file_size') or f.get('size') or 0
                    try: total_size_bytes += int(size_value)
                    except ValueError: pass
                    size_display = str(format_size(size_value))
                    file_type = str(f.get('type')).upper()
                    display_type = "DOSSIER" if file_type == 'FOLDER' else str(f.get('extension') or "file")
                    display_name = str(f.get('name') or "Sans nom")
                    if e2ee_key:
                        if display_name.endswith('.enc'):
                             decrypted = E2EE_decrypt_name(display_name[:-4], e2ee_key)
                             if decrypted != display_name[:-4]: display_name = decrypted
                        else:
                            p_name = Path(display_name)
                            base, ext = p_name.stem, p_name.suffix
                            if base:
                                decrypted_base = E2EE_decrypt_name(base, e2ee_key)
                                if decrypted_base != base: display_name = f"{decrypted_base}{ext}"
                                else:
                                    decrypted_full = E2EE_decrypt_name(display_name, e2ee_key)
                                    if decrypted_full != display_name: display_name = decrypted_full
                    icon_emoji = "📁 " if file_type == 'FOLDER' else "📄 "
                    table_data.append({
                        "nom": icon_emoji + display_name,
                        "taille": size_display,
                        "type": display_type,
                        "modifie": str(format_display_date(f.get('updated_at'))),
                        "file_id": str(f.get('id'))
                    })
                self.table.data = table_data
            loc_name = "Dossier" if current_folder else "Racine"
            total_display = format_size(total_size_bytes)
            self.status.text = f"{count} éléments dans {loc_name} | Taille: {total_display}"
        except Exception as e:
            self.status.text = f"Erreur: {e}"
    def refresh(self, widget): 
        if widget == self.selection_ws:
            self.current_folder_id = None
            self.history = []
        asyncio.create_task(self.load_data())
    def _enter_folder(self, file_id):
        f = next((x for x in self.files_cache if str(x['id']) == file_id), None)
        if f and f.get('type') == 'folder':
            self.history.append(self.current_folder_id)
            self.current_folder_id = file_id
            self.refresh(None)
    def on_table_activate(self, widget, row):
        if hasattr(row, 'file_id'): self._enter_folder(str(row.file_id))
    def on_mobile_select(self, widget, row=None):
        if row is None: row = widget.selection
        if row and hasattr(row, 'id'): self._enter_folder(str(row.id))
    def action_open(self, widget):
        if self.app.is_mobile: return
        sel = self.table.selection
        if not sel: return
        row = sel[0] if isinstance(sel, list) else sel
        if hasattr(row, 'file_id'): self._enter_folder(str(row.file_id))
    def action_up(self, widget):
        if not self.history:
            self.status.text = "Déjà à la racine."
            return
        self.current_folder_id = self.history.pop()
        self.refresh(None)
    def action_back_window(self, widget):
        self.app.retour_arriere(widget)
    def get_selection_list(self):
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
                    found = next((f for f in self.files_cache if str(f['id']) == rid), None)
                    if found: selected_files.append(found)
            except: pass
        return selected_files
    async def action_soft_delete(self, widget):
        files = self.get_selection_list()
        if not files: 
            await self.app.main_window.dialog(toga.InfoDialog("Info", "Rien de sélectionné."))
            return
        confirm = await self.app.main_window.dialog(toga.QuestionDialog("Corbeille", f"Envoyer {len(files)} éléments à la corbeille ?"))
        if not confirm: return
        ids = [str(f['id']) for f in files]
        loop = asyncio.get_running_loop()
        self.status.text = "Suppression en cours..."
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            def do(): 
                try: return self.app.api_client.delete_entries(batch, delete_forever=False)
                except Exception: return None
            await loop.run_in_executor(None, do)
        self.refresh(None)
    async def action_rename(self, widget):
        files = self.get_selection_list()
        if not files: 
            await self.app.main_window.dialog(toga.InfoDialog("Info", "Rien de sélectionné."))
            return
        if len(files) > 1: 
            await self.app.main_window.dialog(toga.InfoDialog("Info", "Veuillez sélectionner un seul fichier à renommer."))
            return
        file = files[0]
        new_name = await self._ask_text_dialog("Renommer", "Nouveau nom :", file['name'])
        if new_name and new_name != file['name']:
            loop = asyncio.get_running_loop()
            def do(): 
                try: return self.app.api_client.rename_entry(file['id'], new_name)
                except Exception: return None
            res = await loop.run_in_executor(None, do)
            if res: self.refresh(None)
            else: await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Le renommage a échoué."))
    async def _ask_text_dialog(self, title, label, initial):
        future = asyncio.Future()
        dlg = toga.Window(title=title, size=(300, 150))
        def on_close(w):
            if not future.done(): future.set_result(None)
            return True
        dlg.on_close = on_close
        box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        box.add(toga.Label(label, style=Pack(margin_bottom=10)))
        inp = toga.TextInput(value=initial, style=Pack(margin_bottom=20))
        box.add(inp)
        def on_ok(w):
            if not future.done(): future.set_result(inp.value)
            dlg.close()
        box.add(toga.Button("Valider", on_press=on_ok, style=Pack(width=260)))
        dlg.content = box
        dlg.show()
        return await future