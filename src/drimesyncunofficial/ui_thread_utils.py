import asyncio
import threading
from typing import Any, Optional

def safe_update_label(app: Any, label: Any, text: str, style_attr: Optional[dict] = None) -> None:
    """
    Met à jour un label Toga de manière thread-safe.
    Vérifie si le widget existe encore avant d'appliquer.
    """
    def _update():
        if not label: return
        try:
            label.text = text
            if style_attr:
                for k, v in style_attr.items():
                    if hasattr(label.style, k):
                        setattr(label.style, k, v)
            if hasattr(label, 'refresh'):
                label.refresh()
        except RuntimeError: pass
        except Exception as e:
            print(f"[UI SAFE] Erreur update label: {e}")

    if app and hasattr(app, 'loop'):
        app.loop.call_soon_threadsafe(_update)

def safe_update_selection(app: Any, selection: Any, value: str) -> None:
    """Met à jour une liste déroulante de manière thread-safe."""
    def _update():
        if not selection: return
        try:
            selection.value = value
        except Exception: pass
    if app and hasattr(app, 'loop'):
        app.loop.call_soon_threadsafe(_update)

def safe_log(app: Any, log_multilinetextutils: Any, message: str, color: str = None) -> None:
    """Ajoute une ligne de log dans un MultilineTextInput de manière thread-safe."""
    def _update():
        if not log_multilinetextutils: return
        try:
            current = log_multilinetextutils.value or ""
            new_line = message
            if color:
                pass 
            log_multilinetextutils.value = current + new_line + "\n"
        except Exception: pass

    if app and hasattr(app, 'loop'):
        app.loop.call_soon_threadsafe(_update)

def run_in_background(target, *args, **kwargs) -> threading.Thread:
    """Lance une fonction dans un thread démon standard (wrapper simple)."""
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
    return t
