import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import COL_GRIS, COL_TEXT_GRIS, COL_VERT, COL_BLEU, COL_JAUNE, COL_ROUGE, CONF_KEY_ENCRYPTION_MODE, CONF_KEY_API_KEY
from drimesyncunofficial.constants import MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK
from drimesyncunofficial.ui_utils import create_back_button
from typing import Any, Optional
from drimesyncunofficial.i18n import tr
class UploadsMenu:
    """
    Menu de sélection des méthodes d'upload (Miroir ou Manuel).
    Redirige dynamiquement vers les gestionnaires chiffrés (E2EE) ou standards
    en fonction du mode de chiffrement configuré.
    """
    def __init__(self, app: Any):
        self.app = app
    def show(self) -> None:
        """Affiche le menu de sélection des uploads."""
        if not self.app.config_data.get(CONF_KEY_API_KEY):
            self.app.loop.create_task(self.app.main_window.dialog(toga.InfoDialog(tr("title_error", "Erreur"), tr("status_key_missing", "Veuillez configurer la clé API."))))
            return
        main_container = toga.ScrollContainer(horizontal=False)
        box = toga.Box(style=Pack(direction=COLUMN, margin=20, flex=1))
        current_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
        mode_mapping = {
            MODE_NO_ENC: (tr("mode_no_enc", "Pas de chiffrement"), COL_BLEU),
            MODE_E2EE_STANDARD: (tr("mode_standard", "Mode Chiffré"), COL_VERT),
            MODE_E2EE_ADVANCED: (tr("mode_advanced", "Mode Chiffré Avancé"), COL_JAUNE),
            MODE_E2EE_ZK: (tr("mode_zk", "Chiffrement Zero Knowledge"), COL_ROUGE),
        }
        mode_label, mode_color = mode_mapping.get(current_mode, (tr("mode_unknown", "Mode Inconnu"), COL_GRIS))
        box.add(create_back_button(self.app.retour_arriere))
        box.add(toga.Divider(style=Pack(margin_bottom=10)))
        content_box = toga.Box(style=Pack(direction=COLUMN, align_items=CENTER, flex=1))
        content_box.add(toga.Label(tr("up_menu_title", "Méthodes d'envoi :"), style=Pack(font_weight=BOLD, margin_bottom=2, text_align='center')))
        content_box.add(toga.Label(
            mode_label, 
            style=Pack(margin_bottom=10, font_weight=BOLD, color=mode_color, font_size=12, text_align='center')
        ))
        buttons_box = toga.Box(style=Pack(direction=COLUMN, width=300))
        btn_mirror = toga.Button(tr("up_btn_mirror", "Miroir Dossier Local"), on_press=self.open_mirror_dispatch, style=Pack(background_color=COL_VERT, color='white', height=50, margin_bottom=10, flex=1))
        btn_files = toga.Button(tr("up_btn_manual", "Sélection Fichiers/Dossiers"), on_press=self.open_manual_dispatch, style=Pack(background_color=COL_BLEU, color='white', height=50, flex=1))
        buttons_box.add(btn_mirror)
        buttons_box.add(btn_files)
        content_box.add(buttons_box)
        box.add(content_box)
        main_container.content = box
        self.app.changer_ecran(main_container)
    def open_mirror_dispatch(self, widget: Any) -> None:
        """Ouvre le gestionnaire de miroir approprié (Standard ou E2EE)."""
        current_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
        is_e2ee = current_mode != MODE_NO_ENC
        if is_e2ee:
            from drimesyncunofficial.uploads_mirror_e2ee import MirrorUploadE2EEManager
            MirrorUploadE2EEManager(self.app).show()
        else:
            from drimesyncunofficial.uploads_mirror import MirrorUploadManager
            MirrorUploadManager(self.app).show()
    def open_manual_dispatch(self, widget: Any) -> None:
        """Ouvre le gestionnaire d'upload manuel approprié (Standard ou E2EE)."""
        current_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
        is_e2ee = current_mode != MODE_NO_ENC
        if is_e2ee:
            from drimesyncunofficial.uploads_manual_e2ee import ManualUploadE2EEManager
            ManualUploadE2EEManager(self.app).show()
        else:
            from drimesyncunofficial.uploads_manual import ManualUploadManager
            ManualUploadManager(self.app).show()