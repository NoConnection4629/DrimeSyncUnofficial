import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, LEFT, RIGHT, BOLD
from drimesyncunofficial.constants import (
    COL_VERT, COL_BLEU, COL_BLEU2, COL_JAUNE, COL_ROUGE, COL_VIOLET, COL_GRIS, COL_TEXT_GRIS, COL_BACKGROUND
)

from drimesyncunofficial.i18n import tr

def create_back_button(on_press, width=100, margin_bottom=10, **style_kwargs):
    """
    Crée un bouton 'Retour' standardisé.
    """
    return toga.Button(
        tr("btn_back", "⬅ Retour"), 
        on_press=on_press, 
        style=Pack(
            width=width, 
            background_color=COL_GRIS, 
            color=COL_TEXT_GRIS, 
            margin_bottom=margin_bottom,
            **style_kwargs
        )
    )

def create_logs_box(readonly=True, flex=1, font_size=8, color=COL_TEXT_GRIS, **style_kwargs):
    """
    Crée une boîte de texte multiligne pour les logs.
    Permet de passer des arguments de style supplémentaires (ex: height, padding).
    """
    return toga.MultilineTextInput(
        readonly=readonly, 
        style=Pack(
            flex=flex, 
            font_size=font_size, 
            color=color,
            **style_kwargs
        )
    )
def create_header_label(text, padding_top=10, padding_bottom=10):
    """Crée un label de titre standardisé (Gras, centré ou gauche selon besoin)."""
    return toga.Label(
        text,
        style=Pack(
            font_weight=BOLD,
            font_size=12,
            margin_top=padding_top,
            margin_bottom=padding_bottom,
            color=COL_TEXT_GRIS
        )
    )
def create_status_label(text="En attente...", color=COL_TEXT_GRIS):
    """Crée un label de statut standard."""
    label = toga.Label(
        text,
        style=Pack(margin=5, color=color, flex=1)
    )
    return label
def create_main_box(style=None):
    """Crée le conteneur principal vertical."""
    if style is None:
        style = Pack(direction=COLUMN, margin=10, background_color=COL_BACKGROUND)
    return toga.Box(style=style)
def create_button(text, on_press, style=None, enabled=True):
    """Crée un bouton standard."""
    if style is None:
        style = Pack(margin=5)
    btn = toga.Button(text, on_press=on_press, style=style)
    btn.enabled = enabled
    return btn

def update_logs_threadsafe(manager, message, color=None):
    """
    Met à jour les logs de l'interface utilisateur depuis n'importe quel thread.
    Logique unifiée pour filtrer les logs DEBUG et supprimer les balises de couleur brute.
    """
    import re
    from datetime import datetime
    
    debug_mode = False
                                                              
    if hasattr(manager, 'app') and hasattr(manager.app, 'config_data'):
        debug_mode = manager.app.config_data.get('debug_mode', False)
    
    msg_str = str(message)
    
                                                  
    if ("[DEBUG]" in msg_str or "[SIMU]" in msg_str) and not debug_mode:
        return

    def _update():
        try:
            prefix = datetime.now().strftime("[%H:%M:%S] ")
            clean_msg = re.sub(r'\[/?(green|red|blue|yellow|cyan|magenta|white|bold|italic|underline)\]', '', msg_str)
            
            if hasattr(manager, 'txt_logs') and manager.txt_logs:
                manager.txt_logs.value += f"{prefix}{clean_msg}\n"
                manager.txt_logs.scroll_to_bottom()
                
            if "TERMINÉ" in clean_msg or "Succès" in clean_msg:
                 if hasattr(manager, 'lbl_status') and manager.lbl_status:
                    manager.lbl_status.text = clean_msg
                    if hasattr(manager.lbl_status, 'style'):
                        manager.lbl_status.style.color = COL_VERT
            elif "Erreur" in clean_msg or "Echec" in clean_msg:
                 if hasattr(manager, 'lbl_status') and manager.lbl_status:
                    manager.lbl_status.text = clean_msg
                    if hasattr(manager.lbl_status, 'style'):
                        manager.lbl_status.style.color = COL_ROUGE
        except (RuntimeError, ValueError): pass

    if hasattr(manager, 'app') and manager.app and hasattr(manager.app, 'loop'):
        manager.app.loop.call_soon_threadsafe(_update)