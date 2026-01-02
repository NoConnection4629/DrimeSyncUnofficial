import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import COL_GRIS, COL_TEXT_GRIS
from drimesyncunofficial.ui_utils import create_back_button
from drimesyncunofficial.i18n import tr

class AboutManager:
    def __init__(self, app):
        self.app = app
        self.window = None
        
    def show(self):
        """Affiche la fenêtre d'aide et de disclaimer."""
        box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        text_view = toga.MultilineTextInput(
            value=tr("about_main_text", "About text"), 
            readonly=True, 
            style=Pack(flex=1, font_family='monospace', margin_bottom=10)
        )
        btn_close = create_back_button(self.app.retour_arriere, margin_bottom=0, margin_top=10)
        box.add(text_view)
        box.add(btn_close)
        self.app.changer_ecran(box)