from drimesyncunofficial.ui_utils import update_logs_threadsafe

class LoggerMixin:
    """
    Mixin pour ajouter des capacités de log standardisées aux Managers.
    """
    def log_ui(self, message: str, color: str = None, debug: bool = False) -> None:
        """
        Affiche un message dans les logs de l'interface graphique de manière thread-safe.
        Tronque automatiquement les messages trop longs (> 500 caractères).
        Si debug=True, le message n'est affiché que si le mode debug est activé dans la config.
        """
        if debug:
            if hasattr(self, 'app') and hasattr(self.app, 'config_data'):
                if not self.app.config_data.get('debug_mode', False):
                    return
            else:
                return                                                       

        msg_str = str(message)
        if len(msg_str) > 500:
             msg_str = msg_str[:500] + "... [TRUNCATED]"
        
        update_logs_threadsafe(self, msg_str, color)

    def log_debug(self, message: str) -> None:
        """Alias pour log_ui(message, debug=True)."""
        self.log_ui(message, debug=True)
