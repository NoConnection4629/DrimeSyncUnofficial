import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import COL_GRIS, COL_TEXT_GRIS, COL_VERT, COL_BLEU, CONF_KEY_API_KEY
from drimesyncunofficial.ui_utils import create_back_button
from drimesyncunofficial.i18n import tr
class DownloadsMenu:
    def __init__(self, app):
        self.app = app
        self.window = None
    def show(self):
        if not self.app.config_data.get(CONF_KEY_API_KEY):
            self.app.loop.create_task(self.app.main_window.dialog(toga.InfoDialog(tr("title_error", "Erreur"), tr("err_api_key_missing", "Veuillez configurer la clé API."))))
            return
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=20, flex=1))
        box.add(create_back_button(self.app.retour_arriere))
        box.add(toga.Divider(style=Pack(margin_bottom=20)))
        content_box = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, flex=1))
        content_box.add(toga.Label(tr("dl_menu_title", "Méthodes de téléchargement :"), style=Pack(font_weight=BOLD, margin_bottom=10, text_align='center')))
        is_e2ee = self.app.config_data.get('e2ee_enabled', False)
        switch_box = toga.Box(style=Pack(direction=ROW, justify_content=CENTER, margin_bottom=20))
        self.chk_mode = toga.Switch(tr("dl_switch_decrypt", "🔒 Déchiffrer les données téléchargées"), value=is_e2ee, on_change=self.on_mode_change)
        switch_box.add(self.chk_mode)
        content_box.add(switch_box)
        buttons_box = toga.Box(style=Pack(direction=COLUMN, width=300))
        btn_ws = toga.Button(tr("dl_btn_workspace", "Tout un Workspace"), on_press=self.open_ws_dispatch, style=Pack(background_color=COL_VERT, color='white', height=50, margin_bottom=10, flex=1))
        btn_manual = toga.Button(tr("dl_btn_manual", "Navigateur de Fichiers"), on_press=self.open_manual_dispatch, style=Pack(background_color=COL_BLEU, color='white', height=50, flex=1))
        buttons_box.add(btn_ws)
        buttons_box.add(btn_manual)
        content_box.add(buttons_box)
        box.add(content_box)
        main_container.content = box
        self.app.changer_ecran(main_container)
    def on_mode_change(self, widget):
        self.app.config_data['e2ee_enabled'] = widget.value
    def open_ws_dispatch(self, widget):
        if self.chk_mode.value:
            from drimesyncunofficial.downloads_workspace_e2ee import WorkspaceDownloadE2EEManager
            WorkspaceDownloadE2EEManager(self.app).show()
        else:
            from drimesyncunofficial.downloads_workspace import WorkspaceDownloadManager
            WorkspaceDownloadManager(self.app).show()
    async def open_manual_dispatch(self, widget):
                                                                         
        try:
            if self.chk_mode.value:
                from drimesyncunofficial.downloads_manual_e2ee import ManualDownloadE2EEManager
                self.active_download_manager = ManualDownloadE2EEManager(self.app)
                self.active_download_manager.show()
            else:
                from drimesyncunofficial.downloads_manual import ManualDownloadManager
                self.active_download_manager = ManualDownloadManager(self.app)
                self.active_download_manager.show()
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.app.main_window.dialog(toga.ErrorDialog(tr("title_error", "Erreur"), f"{tr('err_open_download', 'Erreur ouverture téléchargement :')} {e}"))