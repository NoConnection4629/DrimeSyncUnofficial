
import json
import re
import os
import fnmatch
import hashlib
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Set, Union
import zipfile

from drimesyncunofficial.constants import (
    API_BASE_URL, HTTP_TIMEOUT,
    COL_VERT, COL_BLEU, COL_BLEU2, COL_JAUNE, COL_ROUGE, COL_VIOLET, COL_GRIS, COL_TEXT_GRIS, COL_BACKGROUND,
    EXCLUDE_FILE_NAME, PARTIAL_HASH_CHUNK_SIZE,
    E2EE_CRYPTO_ALGO, MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK
)

from drimesyncunofficial.ui_utils import update_logs_threadsafe

from drimesyncunofficial.format_utils import (
    truncate_path_smart, format_size, format_display_date,
    sanitize_filename_for_upload, restore_filename_from_download
)
import platform

def ensure_long_path_aware(path_str: str) -> str:
    """
    Sur Windows, préfixe le chemin absolu avec '\\\\?\\' pour supporter les chemins longs (>260 chars).
    Sur les autres OS, retourne le chemin tel quel.
    """
    if platform.system() == "Windows":
        try:
             abs_path = str(Path(path_str).resolve())
        except:
             abs_path = os.path.abspath(path_str)
        
        if not abs_path.startswith("\\\\?\\"):
             return f"\\\\?\\{abs_path}"
        return abs_path
    return path_str

from drimesyncunofficial.crypto_utils import (
    get_salt_path, generate_or_load_salt, get_salt_as_base64, save_salt_from_base64,
    derive_key, E2EE_encrypt_file, E2EE_decrypt_file, E2EE_encrypt_bytes, E2EE_decrypt_bytes,
    E2EE_encrypt_name, E2EE_decrypt_name, calculate_encrypted_remote_path, get_remote_path_for_tree_file
)

def update_logs_ui_threadsafe(manager: Any, message: str, color: Optional[str] = None) -> None:
    """
    Façade pour drimesyncunofficial.ui_utils.update_logs_threadsafe
    Sert à ne pas casser le code existant qui importe depuis utils.
    """
    update_logs_threadsafe(manager, message, color)

def get_global_exclusion_path(app_paths: Any) -> Path:
    """
    Retourne le chemin du fichier de règles d'exclusion (.drimesyncignore).
    
    Args:
        app_paths: Objet contenant les chemins de l'application (app.paths).
        
    Returns:
        Path vers le fichier .drimesyncignore dans le dossier data de l'app.
    """
    return Path(app_paths.data) / EXCLUDE_FILE_NAME

def load_exclusion_patterns(app_paths: Any, enabled: bool = True) -> List[str]:
    """
    Charge et parse les motifs d'exclusion (glob patterns) depuis .drimesyncignore.
    
    Crée automatiquement le fichier avec des règles par défaut s'il n'existe pas.
    
    Args:
        app_paths: Objet contenant les chemins de l'application.
        enabled: Si False, retourne une liste vide (désactive les exclusions).
        
    Returns:
        Liste des patterns d'exclusion (format glob). Lignes commentées (#) ignorées.
        
    Example:
        >>> patterns = load_exclusion_patterns(app.paths)
        >>> print(patterns)
        ['*.tmp', '*.log', '__pycache__/', '.git/']
    """
    if not enabled: return []
    path = get_global_exclusion_path(app_paths)
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            default_content = [
                "# --- Fichiers Système ---", "Thumbs.db", "desktop.ini", ".DS_Store", "._*",
                "# --- Fichiers Temporaires ---", "*.tmp", "*.temp", "*.bak", "*.log", "*.swp", "~$*", "*.trashed*", "*.thumbnail*", "*.thumbnails*",
                "# --- Développement ---", "__pycache__/", ".git/", ".svn/", ".idea/", ".vscode/", "node_modules/", "venv/", ".env"
            ]
            path.write_text("\n".join(default_content), encoding="utf-8")
        except: pass
    patterns = []
    if path.exists():
        try:
            patterns = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        except: pass
    return patterns

def get_partial_hash(file_path: Union[str, Path], file_size: int) -> Optional[str]:
    """
    Calcule un hash MD5 partiel (Début + Fin du fichier).
    Permet une identification rapide des gros fichiers sans lecture intégrale.
    """
    m = hashlib.md5()
    m.update(str(file_size).encode('utf-8'))
    try:
        with open(file_path, "rb") as f:
            if file_size <= PARTIAL_HASH_CHUNK_SIZE * 2: m.update(f.read())
            else:
                m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
                f.seek(-PARTIAL_HASH_CHUNK_SIZE, os.SEEK_END)
                m.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
        return m.hexdigest()
    except: return None

def _process_file_worker(file_tuple: Tuple[str, str]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Fonction worker exécutée dans un thread séparé pour scanner un fichier."""
    full_path, rel_path = file_tuple
    try:
        p = Path(full_path)
        st = p.stat()
        ph = get_partial_hash(p, st.st_size)
        if ph:
            return rel_path, {
                "full_path": str(p), 
                "size": st.st_size, 
                "mtime": st.st_mtime, 
                "partial_hash": ph
            }
    except: pass
    return rel_path, None

def scan_local_tree_parallel(root_folder: str, app_paths: Any, use_exclusions: bool = True, nb_workers: int = 5) -> Dict[str, Any]:
    """
    Scanne récursivement un dossier local pour construire l'arbre de synchronisation.
    Utilise un ThreadPoolExecutor pour paralléliser le calcul des hashs.
    """
    tree = {"folders": set(), "files": {}}
    exclusions = load_exclusion_patterns(app_paths, use_exclusions)
    files_to_process = []
    root_path = Path(root_folder)
    for root, dirs, files in os.walk(root_folder):
        for d in dirs[:]:
            full_dir = Path(root) / d
            try:
                rel = str(full_dir.relative_to(root_path)).replace("\\", "/")
            except ValueError: continue
            if any(fnmatch.fnmatch(rel, p) for p in exclusions):
                dirs.remove(d); continue
            tree["folders"].add(rel)
        for f in files:
            full = Path(root) / f
            try:
                rel = str(full.relative_to(root_path)).replace("\\", "/")
            except ValueError: continue
            if any(fnmatch.fnmatch(rel, p) for p in exclusions): continue
            files_to_process.append((str(full), rel))
    actual_workers = max(2, min(nb_workers * 2, 50)) 
    with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {executor.submit(_process_file_worker, ft): ft for ft in files_to_process}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res[1]:
                tree["files"][res[0]] = res[1]
    return tree

def prevent_windows_sleep() -> None:
    """
    Empêche la mise en veille du système (Windows uniquement) pendant les opérations longues.
    Utilise l'API Win32 SetThreadExecutionState.
    """
    import sys
    is_windows = False
    try:
        import toga
        if toga.platform.current_platform == 'windows':
            is_windows = True
    except:
        if sys.platform == 'win32':
            is_windows = True
    if is_windows:
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
        except Exception:
            pass 

def _force_windows_backend() -> None:
    """
    Force l'utilisation du backend Windows Credential Locker pour Keyring.
    Nécessaire pour éviter les conflits avec d'autres backends (ex: fichier chiffré).
    """
    import sys
    if sys.platform != 'win32': return
    try:
        import keyring
        from keyring.backends import Windows
        keyring.set_keyring(Windows.WinVaultKeyring())
    except Exception as e:
        print(f"⚠️ Impossible de forcer le backend Windows : {e}")

def get_secure_secret(key_name: str, default_value: str = "") -> Optional[str]:
    """Récupère un secret stocké de manière sécurisée dans le Keyring de l'OS."""
    try:
        import toga
        if toga.platform.current_platform in {'android', 'iOS'}:
            return None 
    except: pass
    try:
        import keyring
        val = keyring.get_password("DrimeSyncUnofficial", key_name)
        return val if val is not None else default_value
    except Exception as e:
        print(f"❌ Erreur Lecture Keyring: {e}")
        return default_value

def set_secure_secret(key_name: str, value: str) -> bool:
    """Enregistre un secret dans le Keyring de l'OS."""
    try:
        import toga
        if toga.platform.current_platform in {'android', 'iOS'}:
            return False
    except: pass
    try:
        import keyring
        if value:
            keyring.set_password("DrimeSyncUnofficial", key_name, value)
        else:
            try: keyring.delete_password("DrimeSyncUnofficial", key_name)
            except: pass
        print(f"✅ SUCCÈS KEYRING ({keyring.get_keyring().name})")
        return True
    except Exception as e:
        print(f"❌ ÉCHEC ÉCRITURE KEYRING: {e}")
        return False

def generate_2fa_secret() -> str:
    """Génère une clé secrète aléatoire (Base32) pour le TOTP."""
    import pyotp
    return pyotp.random_base32()

def verify_2fa_code(secret: str, code: str) -> bool:
    """Vérifie la validité d'un code TOTP par rapport au secret."""
    if not secret or not code: return False
    try:
        import pyotp
        missing_padding = len(secret) % 8
        if missing_padding != 0:
            secret += '=' * (8 - missing_padding)
            
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=2)
    except: return False

def generate_qr_image_bytes(secret: str, account_name: str = "DrimeSync User") -> bytes:
    """
    Génère une image PNG contenant le QR Code de configuration 2FA.
    Retourne les octets de l'image pour affichage direct dans Toga.
    """
    import pyotp
    import qrcode
    import io
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=account_name, issuer_name="DrimeSync Unofficial")
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

def get_total_size(path_str: str) -> int:
    """Calcul la taille totale d'un fichier ou d'un dossier récursivement."""
    try:
        p = Path(path_str)
        if p.is_file():
            return p.stat().st_size
        elif p.is_dir():
            return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
    except Exception as e:
        print(f"Erreur calcul taille: {e}")
    return 0

def make_zip(source_dir: Union[str, Path], output_filename: Union[str, Path]) -> bool:
    """Crée une archive ZIP d'un dossier complet."""
    try:
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(str(source_dir)):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=str(source_dir))
                    zipf.write(file_path, arcname)
        return True
    except Exception as e:
        print(f"Zip Error: {e}")
        return False

def validate_password_compliance(password: str) -> bool:
    """
    Vérifie si le mot de passe respecte les critères de complexité (ANSSI).
    - 12 caractères min
    - 1 Majuscule, 1 Minuscule, 1 Chiffre, 1 Spécial
    """
    if len(password) < 12: return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[ !@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password): return False
    return True

