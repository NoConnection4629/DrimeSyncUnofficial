
import os
import hashlib
from pathlib import Path
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Optional, Any, Union


import nacl.pwhash
import nacl.utils
import nacl.hash
import nacl.encoding
from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_encrypt,
    crypto_aead_xchacha20poly1305_ietf_decrypt
)
from nacl.exceptions import CryptoError

from drimesyncunofficial.constants import (
    E2EE_SALT_PATH, SYNC_STATE_FOLDER_NAME, CLOUD_TREE_FILE_NAME,
    MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK
)
from drimesyncunofficial.format_utils import sanitize_filename_for_upload


def get_salt_path(app_paths: Any) -> Path: 
    """Retourne le chemin absolu du fichier contenant le sel cryptographique."""
    return Path(app_paths.data) / E2EE_SALT_PATH

def generate_or_load_salt(app_paths: Any) -> Optional[bytes]:
    """
    Récupère le sel existant ou en génère un nouveau (16 octets aléatoires).
    Le sel est indispensable pour dériver la clé de chiffrement de manière sécurisée.
    """
    salt_file_path = get_salt_path(app_paths)
    if not salt_file_path.parent.exists():
        try: salt_file_path.parent.mkdir(parents=True, exist_ok=True)
        except: pass
    if salt_file_path.exists():
        try:
            return salt_file_path.read_bytes()
        except: pass
    salt = os.urandom(16)
    try:
        salt_file_path.write_bytes(salt)
    except: return None
    return salt

def get_salt_as_base64(app_paths: Any) -> Optional[str]:
    """Retourne le sel actuel sous forme de string Base64 pour export."""
    salt = generate_or_load_salt(app_paths)
    if salt:
        return urlsafe_b64encode(salt).decode('utf-8')
    return None

def save_salt_from_base64(app_paths: Any, salt_b64: str) -> bool:
    """
    Importe un sel depuis une string Base64.
    ATTENTION : Écrase le sel existant. Vérifier l'input avant d'appeler.
    """
    try:
        salt_bytes = urlsafe_b64decode(salt_b64)
        if len(salt_bytes) != 16: return False                           
        salt_path = get_salt_path(app_paths)
        salt_path.write_bytes(salt_bytes)
        return True
    except: return False

def derive_key(password: str, salt: bytes) -> bytes:
    """
    Dérive une clé de chiffrement (32 bytes) à partir du mot de passe utilisateur.
    MIGRATION v1.3.1 : Utilise Argon2id (via PyNaCl) au lieu de PBKDF2.
    """
    kdf = nacl.pwhash.argon2id.kdf
    opslimit = nacl.pwhash.OPSLIMIT_MODERATE
    memlimit = nacl.pwhash.MEMLIMIT_MODERATE
    
    KEY_SIZE = 32

    try:
        key = kdf(
            KEY_SIZE, 
            password.encode('utf-8'), 
            salt,
            opslimit=opslimit,
            memlimit=memlimit
        )
        return key
    except Exception as e:
        print(f"KDF Erreur: {e}")
        return kdf(KEY_SIZE, password.encode('utf-8'), salt, 
                   opslimit=nacl.pwhash.OPSLIMIT_MIN, memlimit=nacl.pwhash.MEMLIMIT_MIN)

def E2EE_encrypt_file(file_path: Union[str, Path], key: bytes) -> bytes:
    """
    Chiffre un fichier complet en utilisant XChaCha20-Poly1305.
    Le nonce (24 octets) est généré aléatoirement et préfixé au ciphertext.
    """
    data = Path(file_path).read_bytes()
    nonce = os.urandom(24)
    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(data, None, nonce, key)
    return nonce + ciphertext

def E2EE_decrypt_file(data: bytes, key: bytes) -> Optional[bytes]:
    """
    Déchiffre un blob de données (fichier complet) chiffré avec XChaCha20-Poly1305.
    Le nonce est extrait automatiquement (24 premiers octets).
    """
    try:
        if len(data) < 24: return None
        nonce = data[:24]
        ciphertext = data[24:]
        decrypted = crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, nonce, key)
        return decrypted
    except Exception: 
        return None

def E2EE_encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Chiffre des données binaires en mémoire (XChaCha20-Poly1305)."""
    nonce = os.urandom(24)
    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(data, None, nonce, key)
    return nonce + ciphertext

def E2EE_decrypt_bytes(data: bytes, key: bytes) -> Optional[bytes]:
    """Déchiffre des données binaires en mémoire (XChaCha20-Poly1305)."""
    try:
        if len(data) < 24: return None
        nonce = data[:24]
        ciphertext = data[24:]
        return crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, nonce, key)
    except Exception:
        return None

def _get_siv_key(key: bytes) -> bytes:
    """Legacy helper unused now."""
    return key

def E2EE_encrypt_name(name: str, key: bytes) -> str:
    """
    Chiffre un nom de fichier/dossier de manière déterministe avec XChaCha20.
    REMPLACEMENT AES-SIV / XSalsa20 : On utilise un nonce synthétique BLAKE2b.
    Nonce = BLAKE2b(name, key=key)[:24]
    """
    if not name or name in [".", ".."]: return name
    try:
        nonce = nacl.hash.blake2b(name.encode('utf-8'), key=key, digest_size=24, encoder=nacl.encoding.RawEncoder)
        
        ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(name.encode('utf-8'), None, nonce, key)
        
        full_enc = nonce + ciphertext
        
        return urlsafe_b64encode(full_enc).decode('utf-8').rstrip('=')
    except Exception as e: 
        return name

def E2EE_decrypt_name(encrypted_name: str, key: bytes) -> str:
    """Déchiffre un nom (Base64 URL-Safe) chiffré avec Deterministic XChaCha20."""
    if not encrypted_name: return encrypted_name
    try:
        padding = '=' * (4 - len(encrypted_name) % 4)
        encrypted_bytes = urlsafe_b64decode(encrypted_name + padding)
        
        if len(encrypted_bytes) < 24: return encrypted_name
        
        nonce = encrypted_bytes[:24]
        ciphertext = encrypted_bytes[24:]
        
        plaintext = crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, nonce, key)
        return plaintext.decode('utf-8')
    except Exception: return encrypted_name

def calculate_encrypted_remote_path(rel_path: str, mode: str, key: bytes, is_folder: bool = False) -> str:
    """
    Calcule le chemin distant complet en appliquant le chiffrement selon le mode choisi.
    - ZK : Tout est chiffré.
    - Advanced : Noms chiffrés, extensions claires (sauf dossiers).
    """
    parts = rel_path.replace("\\", "/").split("/")
    processed_parts = []
    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        should_encrypt = False
        if mode == MODE_E2EE_ZK: should_encrypt = True
        elif mode == MODE_E2EE_ADVANCED:
            if is_last and not is_folder: should_encrypt = True
        if should_encrypt:
            if is_last and not is_folder and mode == MODE_E2EE_ADVANCED:
                p = Path(part)
                base, ext = p.stem, p.suffix
                enc_base = E2EE_encrypt_name(base, key)
                processed_parts.append(f"{enc_base}{ext}")
            else:
                processed_parts.append(E2EE_encrypt_name(part, key))
        else:
            processed_parts.append(sanitize_filename_for_upload(part))
    return "/".join(processed_parts)

def get_remote_path_for_tree_file(mode: str, key: bytes) -> str:
    """Détermine l'emplacement du fichier d'index de synchronisation selon le mode de chiffrement."""
    filename = CLOUD_TREE_FILE_NAME
    folder = SYNC_STATE_FOLDER_NAME
    if mode in [MODE_NO_ENC, MODE_E2EE_STANDARD]: return f"{folder}/{filename}"
    elif mode == MODE_E2EE_ADVANCED: return f"{folder}/{E2EE_encrypt_name(filename, key)}"
    elif mode == MODE_E2EE_ZK: return f"{E2EE_encrypt_name(folder, key)}/{E2EE_encrypt_name(filename, key)}"
    return f"{folder}/{filename}"
