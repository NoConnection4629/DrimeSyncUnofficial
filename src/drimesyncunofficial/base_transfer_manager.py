import toga
import threading
import time
from typing import Optional, Any, TYPE_CHECKING
from toga.style import Pack
from toga.style.pack import ROW, COLUMN
from drimesyncunofficial.constants import COL_JAUNE, COL_VERT, COL_ROUGE, COL_BLEU
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background
from drimesyncunofficial.android_utils import acquire_wakelock, release_wakelock

if TYPE_CHECKING:
    from drimesyncunofficial.app import DrimeSyncUnofficial

class BaseTransferManager(LoggerMixin):
    """
    Classe de base pour les gestionnaires de transferts (Upload/Download).
    Gère l'état (Running, Paused, Cancelled), les logs et les contrôles UI standards.
    """
    def __init__(self, app: "DrimeSyncUnofficial") -> None:
        self.app: "DrimeSyncUnofficial" = app
        self.is_running: bool = False
        self.is_paused: bool = False
        self.is_cancelled: bool = False
        self.stop_event: threading.Event = threading.Event()
        
                                                       
        self.btn_pause: Optional[toga.Button] = None
        self.btn_cancel: Optional[toga.Button] = None
        self.lbl_progress: Optional[toga.Label] = None
        self.box_controls: Optional[toga.Box] = None
        self.box_actions_container: Optional[toga.Box] = None                                                      
        self.btn_action_main: Optional[toga.Button] = None                                                       

                        
        self.last_text: str = ""

    def action_toggle_pause(self, widget: Any) -> None:
        """Bascule l'état de pause."""
        if not self.is_running: return
        
        if self.is_paused:
            self.is_paused = False
            if self.btn_pause:
                self.btn_pause.text = "⏸️ Pause"
                self.btn_pause.style.background_color = COL_JAUNE
            self.update_status_ui("Reprise...", COL_JAUNE)
            self.log_ui("Reprise du transfert.", "green")
        else:
            self.is_paused = True
            if self.btn_pause:
                self.btn_pause.text = "▶️ Reprendre"
                self.btn_pause.style.background_color = COL_VERT
            self.update_status_ui("EN PAUSE", COL_JAUNE)
            self.log_ui("Transfert mis en pause.", "yellow")

    def action_cancel(self, widget: Any) -> None:
        """Demande l'annulation du transfert."""
        if not self.is_running: return
        
        self.is_cancelled = True
        self.is_paused = False                             
        self.stop_event.set()
        
        self.update_status_ui("Annulation en cours...", COL_ROUGE)
        self.log_ui("Annulation demandée...", "red")
        
        if self.btn_pause: self.btn_pause.enabled = False
        if self.btn_cancel: self.btn_cancel.enabled = False

    def update_status_ui(self, text: str, color: Optional[str] = None) -> None:
        """Met à jour le label de statut (thread-safe via ui_thread_utils)."""
        self.last_text = text
        if not self.is_running and "Terminé" not in text and "Annulé" not in text and "Reprise" not in text:
            return
        
        style = {'color': color} if color else None
        safe_update_label(self.app, self.lbl_progress, text, style)

    def _set_ui_running(self, running: bool) -> None:
        """
        Active/Désactive le mode 'En cours' de l'UI.
        Gère la visibilité des contrôles (Pause/Cancel) vs Actions (Envoyer).
        """
        self.is_running = running
        if running:
            self.stop_event.clear()
            self.is_cancelled = False
            self.is_paused = False
            acquire_wakelock("DrimeSync:TransferManager")
        
        def _upd():
            if running:
                                                  
                if self.box_actions_container:
                    self.box_actions_container.style.visibility = 'hidden'
                    self.box_actions_container.style.height = 0
                    self.box_actions_container.style.width = 0 
                elif self.btn_action_main:                               
                    self.btn_action_main.style.visibility = 'hidden'
                    self.btn_action_main.style.height = 0
                    self.btn_action_main.style.width = 0

                                        
                if self.box_controls:
                    self.box_controls.style.visibility = 'visible'
                    self.box_controls.style.height = 50
                    try: del self.box_controls.style.width 
                    except: pass
                
                if self.btn_pause:
                    self.btn_pause.style.visibility = 'visible'
                    self.btn_pause.text = "⏸️ Pause"
                    self.btn_pause.style.background_color = COL_JAUNE
                    self.btn_pause.enabled = True
                    
                if self.btn_cancel:
                    self.btn_cancel.style.visibility = 'visible'
                    self.btn_cancel.enabled = True

            else:
                release_wakelock()
                                       
                if self.box_controls:
                    self.box_controls.style.visibility = 'hidden'
                    self.box_controls.style.height = 0
                    self.box_controls.style.width = 0

                                        
                if self.box_actions_container:
                    self.box_actions_container.style.visibility = 'visible'
                    try: del self.box_actions_container.style.height
                    except: pass
                    try: del self.box_actions_container.style.width
                    except: pass
                elif self.btn_action_main:
                    self.btn_action_main.style.visibility = 'visible'
                    try: del self.btn_action_main.style.height
                    except: pass
                    try: del self.btn_action_main.style.width
                    except: pass
                    self.btn_action_main.style.height = 50

                final_text = "Terminé." if not self.is_cancelled else "Annulé."
                color = COL_VERT if not self.is_cancelled else COL_ROUGE
                                                                                       
                self.last_text = final_text 
                if self.lbl_progress:
                    self.lbl_progress.text = final_text
                    self.lbl_progress.style.color = color
                    
            if hasattr(self.app.main_window, 'content'):
                self.app.main_window.content.refresh()
                
        self.app.loop.call_soon_threadsafe(_upd)

    def check_wait_pause(self) -> bool:
        """
        Vérifie si une pause est active et attend.
        Retourne True si on doit continuer, False si annulé pendant la pause.
        """
        while self.is_paused and not self.is_cancelled and not self.stop_event.is_set():
            time.sleep(0.5)
        return not (self.is_cancelled or self.stop_event.is_set())
