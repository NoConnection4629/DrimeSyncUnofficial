import toga
import sys

_wake_lock = None

def get_android_context():
    """ Récupère l'activité Android courante de manière robuste (Toga/BeeWare). """
    try:
        app = toga.App.app
        if hasattr(app, '_impl') and hasattr(app._impl, 'native'):
            return app._impl.native
    except: pass

    try:
        from android.app import Activity
        return Activity.mActivity
    except: pass
    
    return None

def acquire_wakelock(tag="DrimeSyncUnofficial:BackgroundWork"):
    """
    Acquiert un PARTIAL_WAKELOCK pour garder le CPU éveillé.
    Nécessite la permission WAKE_LOCK dans le buildozer.spec (déjà standard souvent).
    """
    global _wake_lock
    if toga.platform.current_platform != 'android':
        return False

    if _wake_lock and _wake_lock.isHeld():
        return True

    try:
        from android.content import Context
        from android.os import PowerManager
        
        activity = get_android_context()
        if not activity: return False

        power_manager = activity.getSystemService(Context.POWER_SERVICE)
        
        _wake_lock = power_manager.newWakeLock(1, tag)
        _wake_lock.acquire()
        print(f"[ANDROID] WakeLock '{tag}' acquired.")
        return True
    except Exception as e:
        print(f"[ANDROID] Erreur acquire_wakelock: {e}")
        return False

def release_wakelock():
    """ Relâche le WakeLock si détenu. """
    global _wake_lock
    if not _wake_lock: return

    try:
        if _wake_lock.isHeld():
            _wake_lock.release()
            print("[ANDROID] WakeLock released.")
        _wake_lock = None
    except Exception as e:
        print(f"[ANDROID] Erreur release_wakelock: {e}")

def is_ignoring_battery_optimizations():
    """ Vérifie si l'app est déjà exemptée. """
    if toga.platform.current_platform != 'android':
        return False
    try:
        from android.content import Context
        from android.os import PowerManager
        
        activity = get_android_context()
        if not activity: return False

        pm = activity.getSystemService(Context.POWER_SERVICE)
        pkg_name = activity.getPackageName()
        return pm.isIgnoringBatteryOptimizations(pkg_name)
    except Exception as e:
        print(f"[ANDROID] Erreur check battery opt: {e}")
        return False

def request_ignore_battery_optimizations_intent():
    """ 
    Lance l'intent pour demander l'exemption. 
    Note: Google Play n'aime pas trop ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS 
    si ce n'est pas justifié, mais pour une app perso/distribuée manuellement c'est OK.
    Sinon utiliser ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS (plus safe).
    Ici on tente le direct car plus efficace pour l'user.
    """
    if toga.platform.current_platform != 'android':
        return

    activity = get_android_context()
    if not activity: 
        return False, "Impossible de récupérer l'activité Android (Context is None)."

    try:
        from android.content import Intent
        from android.net import Uri
        from android.provider import Settings
        
        intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
        package_uri = Uri.parse("package:" + activity.getPackageName())
        intent.setData(package_uri)
        
        activity.startActivity(intent)
        return True, "Demande envoyée (Direct)."
    except Exception as e:
        err_log = f"{e}"
        print(f"[ANDROID] Erreur intent battery: {e}")
        try:
            intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
            activity.startActivity(intent)
            return True, "Ouverture écran paramètres (Fallback)."
        except Exception as e2:
             return False, f"Echec total: {err_log} | Fallback: {e2}"

def copy_to_clipboard_android(text):
    """ Copie du texte dans le presse-papier Android nativement. """
    if toga.platform.current_platform != 'android': return False
    try:
        from android.content import Context, ClipData
        activity = get_android_context()
        if not activity: return False

        clipboard = activity.getSystemService(Context.CLIPBOARD_SERVICE)
        clip = ClipData.newPlainText("Copied Text", text)
        clipboard.setPrimaryClip(clip)
        return True
    except Exception as e:
        print(f"[ANDROID] Clipboard error: {e}")
        return False
