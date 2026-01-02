import asyncio
import os
import time
import tempfile
import random
from pathlib import Path
from typing import Dict, Any, Optional

import toga
from drimesyncunofficial.base_download_manager import BaseDownloadManager
from drimesyncunofficial.constants import (
    COL_VERT, COL_ROUGE, COL_BLEU2,
    MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK,
    CONF_KEY_ENCRYPTION_MODE, CONF_KEY_E2EE_PASSWORD
)
from drimesyncunofficial.utils import (
    generate_or_load_salt, derive_key, E2EE_decrypt_name, E2EE_decrypt_file, format_size
)
from drimesyncunofficial.i18n import tr

class ManualDownloadE2EEManager(BaseDownloadManager):
    def __init__(self, app: Any):
        super().__init__(app)
        self.e2ee_mode: str = MODE_NO_ENC
        self.e2ee_password: str = ""
        self.e2ee_key: Optional[bytes] = None

    def show(self) -> None:
        try:
            self.app.config_data = self.app.charger_config()
            self.e2ee_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
            self.e2ee_password = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
            if self.e2ee_mode == MODE_NO_ENC: self.e2ee_mode = MODE_E2EE_STANDARD
        except: pass

        if not self.e2ee_password:
             self.app.main_window.dialog(toga.ErrorDialog(tr("sec_2fa_config_req", "Configuration Requise"), tr("err_pwd_missing", "Mot de passe E2EE manquant.")))
             return
        
        try:
             salt = generate_or_load_salt(self.app.paths)
             if not salt:
                 self.app.main_window.dialog(toga.ErrorDialog(tr("sec_err_salt_missing", "Erreur Sel"), tr("err_salt_missing", "Impossible de charger le sel.")))
                 return
             self.e2ee_key = derive_key(str(self.e2ee_password), salt)
        except Exception as e:
             self.app.main_window.dialog(toga.ErrorDialog(tr("sec_err_key", "Erreur Clé"), f"{tr('sec_err_detail', 'Détail')}: {e}"))
             return

        super()._init_ui(title=tr("dl_manual_e2ee_title", "DOWNLOAD MANUEL E2EE"), title_color=COL_VERT)
    
    def _process_file_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Déchiffre le nom du fichier pour l'affichage et le traitement."""
        raw_name = item.get('name', '')
        dec_name = raw_name
        try:
            if self.e2ee_mode == MODE_E2EE_ZK and raw_name.endswith('.enc'):
                dec_name = E2EE_decrypt_name(raw_name[:-4], self.e2ee_key)
            elif self.e2ee_mode == MODE_E2EE_ADVANCED:
                p = Path(raw_name)
                dec_base = E2EE_decrypt_name(p.stem, self.e2ee_key)
                dec_name = f"{dec_base}{p.suffix}" if dec_base else raw_name
            else:
                dec_name = E2EE_decrypt_name(raw_name, self.e2ee_key)
            
            if not dec_name: dec_name = raw_name
        except:
             dec_name = raw_name
        
        new_item = item.copy()
        new_item['name'] = dec_name
        return new_item

    def _download_file_worker(self, url: str, save_path: str, file_name: str, total_size: int) -> tuple[bool, str, int]:
        """Override: Download Encrypted -> Temp -> Decrypt -> Save"""
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                if attempt == 0: time.sleep(random.uniform(0.1, 0.5))
                
                with self.app.api_client.get_download_stream(url) as r:
                    if r.status_code == 404: return False, "404 Not Found", 0
                    if r.status_code in [403, 429]:
                        if attempt < max_retries - 1:
                            wait_time = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                            self.log_ui(f"{tr('err_403_429_pause', '⚠️ [403/429] Trop de requêtes. Pause')} {wait_time:.1f}s...", "yellow")
                            time.sleep(wait_time)
                            continue
                        else:
                            return False, f"{tr('err_max_retries', 'Erreur (Max retries)')} {r.status_code}", 0

                    r.raise_for_status()
                    if total_size == 0 and r.headers.get('content-length'): 
                        total_size = int(r.headers.get('content-length'))
                    
                    last_update = 0
                    downloaded_chunk = 0
                    
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_enc:
                        tmp_enc_path = tmp_enc.name
                        for chunk in r.iter_content(chunk_size=self.DOWNLOAD_CHUNK_SIZE):
                            if self.is_cancelled:
                                r.close(); tmp_enc.close()
                                try: Path(tmp_enc_path).unlink(missing_ok=True)
                                except: pass
                                return False, tr("status_cancelled", "Annulé"), 0
                            
                            while self.is_paused: time.sleep(0.5)
                            
                            if chunk:
                                tmp_enc.write(chunk)
                                l = len(chunk)
                                downloaded_chunk += l
                                
                                if hasattr(self, 'total_downloaded_bytes'):
                                     self.total_downloaded_bytes += l
                                
                    
                    if not self.is_cancelled:
                        try:
                            enc_bytes = Path(tmp_enc_path).read_bytes()
                            decrypted_data = E2EE_decrypt_file(enc_bytes, self.e2ee_key)
                            
                            if decrypted_data is not None:
                                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                with open(save_path, 'wb') as f_out:
                                    f_out.write(decrypted_data)
                            else:
                                if os.path.exists(tmp_enc_path): os.unlink(tmp_enc_path)
                                return False, tr("err_decryption", "Erreur déchiffrement"), 0
                        except Exception as e:
                            if os.path.exists(tmp_enc_path): os.unlink(tmp_enc_path)
                            return False, f"{tr('exc_decryption', 'Exception déchiffrement :')} {e}", 0

                    if os.path.exists(tmp_enc_path): os.unlink(tmp_enc_path)
                    return True, "OK", total_size
            
            except Exception as e:
                if attempt < max_retries - 1:
                     wait = (base_delay * (attempt + 1)) + random.uniform(0, 0.5)
                     time.sleep(wait)
                else:
                    try: Path(save_path).unlink(missing_ok=True)
                    except: pass
                    return False, str(e), 0
        
        return False, "Failed", 0