import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD
from drimesyncunofficial.constants import COL_GRIS, COL_TEXT_GRIS, COL_BLEU2, COL_JAUNE
from drimesyncunofficial.ui_utils import create_back_button
from drimesyncunofficial.i18n import tr

class AboutFiligranageManager:
    def __init__(self, app):
        self.app = app
        self.window = None
        
    def show(self):
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=15))

        nav_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10, align_items=CENTER))
        btn_back = create_back_button(self.app.retour_arriere, width=100, margin_bottom=0, margin_right=10)
        nav_box.add(btn_back)
        main_box.add(nav_box)
        
        title_lbl = toga.Label(tr("about_notice_watermark", "NOTICE - FILIGRANAGE"), style=Pack(font_size=16, font_weight=BOLD, color=COL_BLEU2, text_align=CENTER, margin_bottom=15))
        main_box.add(title_lbl)

        text_view = toga.MultilineTextInput(
            value=tr("about_filigranage_text", "Watermark guide"), 
            readonly=True, 
            style=Pack(flex=1, font_family='sans-serif', margin_bottom=10)
        )
        main_box.add(text_view)

        self.app.changer_ecran(main_box)