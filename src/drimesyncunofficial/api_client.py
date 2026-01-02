import requests
import os
import math
import mimetypes
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable
from drimesyncunofficial.constants import API_BASE_URL, HTTP_TIMEOUT, CHUNK_SIZE, BATCH_SIZE, PART_UPLOAD_RETRIES

class DrimeError(Exception):
    """Base exception for all DrimeSync errors."""
    pass

class DrimeNetworkError(DrimeError):
    """Network related errors (Connection refused, Timeout, DNS...)."""
    pass

class DrimeAuthError(DrimeError):
    """Authentication errors (401, 403)."""
    pass

class DrimeServerError(DrimeError):
    """Server side errors (500+)."""
    pass

class DrimeClientError(DrimeError):
    """Client side logic errors (400, 404, 429...)."""
    pass

class DrimeAPIClient:
    """
    Client centralisé pour l'API Drime.
    Gère l'authentification, les requêtes HTTP, et les opérations spécifiques (Upload, Download, Gestion de fichiers).
    """
    def __init__(self, api_key: str, api_base_url: str = API_BASE_URL):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self.session.headers.update(self.headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Wrapper centralisé pour toutes les requêtes API.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.api_base_url}{endpoint}"
        
        is_android = False
        try:
            import toga
            if toga.platform.current_platform == 'android': is_android = True
        except: pass
        
        retries = 1 if is_android else 0
        
        while retries >= 0:
            try:
                resp = self.session.request(method, url, timeout=kwargs.pop('timeout', HTTP_TIMEOUT), **kwargs)
                return resp
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                if is_android and retries > 0:
                     print(f"[RESEAU] Echec {e}. Reset Session sur Android...")
                     self.session.close()
                     self.session = requests.Session()
                     self.session.headers.update(self.headers)
                     retries -= 1
                     time.sleep(1)
                     continue
                
                raise DrimeNetworkError("Erreur de connexion : Impossible de joindre le serveur.")
            except requests.exceptions.Timeout:
                raise DrimeNetworkError("Délai d'attente dépassé (Timeout).")
            except requests.exceptions.RequestException as e:
                raise DrimeNetworkError(f"Erreur réseau inattendue : {e}")
        
        raise DrimeNetworkError("Impossible de se connecter après toutes les tentatives.")

    def _handle_response(self, resp: requests.Response) -> requests.Response:
        """Analyse le code de statut et lève l'exception appropriée si erreur."""
        if 200 <= resp.status_code < 300:
            return resp
        
                              
        msg = f"Erreur HTTP {resp.status_code}"
        try:
            error_json = resp.json()
            if isinstance(error_json, dict) and 'message' in error_json:
                msg = f"{msg}: {error_json['message']}"
        except: pass

        if resp.status_code == 401 or resp.status_code == 403:
            raise DrimeAuthError(msg)
        elif 400 <= resp.status_code < 500:
            raise DrimeClientError(msg)
        elif resp.status_code >= 500:
            print(f"[API DEBUG] 500 Error Body: {resp.text}")
            raise DrimeServerError(msg)
        
        return resp

    def request_json(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Exécute une requête HTTP et retourne le JSON décodé.
        
        Args:
            method: Méthode HTTP (GET, POST, PUT, DELETE).
            endpoint: Point de terminaison de l'API (ex: '/workspaces').
            **kwargs: Arguments additionnels passés à requests (json, data, params, etc.).
            
        Returns:
            Objet Python décodé depuis le JSON de réponse. None si status 204.
            
        Raises:
            DrimeNetworkError: En cas d'erreur réseau (timeout, connexion refusée).
            DrimeAuthError: Si authentification échoue (401, 403).
            DrimeClientError: Pour erreurs client (400, 404, 429).
            DrimeServerError: Pour erreurs serveur (500+).
        """
        resp = self._request(method, endpoint, **kwargs)
        self._handle_response(resp)
        if resp.status_code == 204: return None
        return resp.json()

    def request_void(self, method: str, endpoint: str, **kwargs) -> None:
        """Exécute une requête attendue sans retour (204 ou 200 avec body ignoré)."""
        resp = self._request(method, endpoint, **kwargs)
        self._handle_response(resp)

    def set_api_key(self, api_key: str) -> None:
        """
        Met à jour la clé API et réinitialise les headers d'authentification.
        
        Utilisé quand l'utilisateur change de compte ou renouvelle sa clé.
        
        Args:
            api_key: Nouvelle clé API Drime.
            
        Example:
            >>> client.set_api_key("new_key_abc123")
        """
        self.api_key = api_key
        self.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers.update(self.headers)

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste publique des workspaces disponibles.
        
        Returns:
            Liste de dictionnaires contenant les infos de chaque workspace.
            Liste vide en cas d'erreur.
            
        Example:
            >>> client = DrimeAPIClient("my_api_key")
            >>> workspaces = client.get_workspaces()
            >>> print(workspaces[0]['name'])
            'Mon Workspace'
        """
        try:
            return self.request_json('GET', '/workspaces') or []
        except DrimeError as e:
            print(f"[API] Erreur get_workspaces: {e}")
            return []

    def get_my_workspaces(self) -> Optional[Dict[str, Any]]:
        """Récupère les workspaces auxquels l'utilisateur a accès."""
        try:
            return self.request_json('GET', '/me/workspaces')
        except DrimeError as e:
            print(f"[API] Erreur get_my_workspaces: {e}")
            return None

    def get_logged_user(self) -> Optional[Dict[str, Any]]:
        """
        Vérifie la validité de la clé API et retourne les infos de l'utilisateur.
        Utilisé au démarrage pour valider la connexion.
        """
        try:
            resp = self.session.get(f"{self.api_base_url}/cli/loggedUser", timeout=HTTP_TIMEOUT)
            if resp.status_code in [200, 201, 204]:
                return resp.json()
            return None
        except Exception as e:
            print(f"[API] Erreur get_logged_user: {e}")
            return None

    def create_entry(self, data: Dict[str, Any]) -> requests.Response:
        """Crée une entrée de fichier ou dossier via l'API S3 (Interne)."""
        return self.session.post(
            f"{self.api_base_url}/s3/entries",
            json=data,
            timeout=HTTP_TIMEOUT
        )

    def upload_simple(self, file_path: str, workspace_id: str, relative_path: str, custom_file_name: Optional[str] = None) -> requests.Response:
        """
        Effectue un upload simple (non-multipart) pour les petits fichiers.
        Utilise le endpoint standard /uploads.
        """
        file_name = custom_file_name if custom_file_name else os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_name)[0]
        if not mime_type: mime_type = "application/octet-stream"
        with open(file_path, 'rb') as f:
            return self.session.post(
                f"{self.api_base_url}/uploads",
                files={"file": (file_name, f, mime_type)},
                data={"relativePath": relative_path, "workspaceId": workspace_id},
                timeout=HTTP_TIMEOUT * 2
            )

    def upload_multipart_init(self, file_name: str, file_size: int, relative_path: str, workspace_id: str) -> requests.Response:
        """
        Initialise une session d'upload multipart (S3).
        Retourne l'uploadId et la clé nécessaire pour la suite.
        """
        return self.session.post(
            f"{self.api_base_url}/s3/multipart/create", 
            json={
                "filename": file_name,
                "mime": "application/octet-stream",
                "size": file_size,
                "extension": os.path.splitext(file_name)[1].lstrip('.'),
                "relativePath": relative_path,
                "workspaceId": workspace_id
            },
            timeout=HTTP_TIMEOUT
        )

    def upload_multipart_sign_batch(self, key: str, upload_id: str, part_numbers: List[int]) -> requests.Response:
        """
        Obtient les URLs signées pour un lot de parties (chunks).
        Permet d'uploader les chunks directement vers le stockage objet.
        """
        return self.session.post(
            f"{self.api_base_url}/s3/multipart/batch-sign-part-urls",
            json={"key": key, "uploadId": upload_id, "partNumbers": part_numbers},
            timeout=HTTP_TIMEOUT
        )

    def upload_multipart_put_chunk(self, url: str, chunk: bytes) -> requests.Response:
        """
        Envoie un chunk de données vers l'URL signée (PUT direct).
        """
        return requests.put(
            url,
            data=chunk,
            headers={"Content-Type": "application/octet-stream"},
            timeout=HTTP_TIMEOUT
        )

    def upload_multipart_complete(self, key: str, upload_id: str, parts: List[Dict[str, Any]]) -> requests.Response:
        """
        Finalise l'upload multipart une fois tous les chunks envoyés.
        Assemble le fichier côté serveur.
        """
        return self.session.post(
            f"{self.api_base_url}/s3/multipart/complete", 
            json={"key": key, "uploadId": upload_id, "parts": parts},
            timeout=HTTP_TIMEOUT
        )
    
    def upload_file(
        self,
        file_path: str,
        workspace_id: str,
        relative_path: str,
        progress_callback: Optional[Callable[[int], None]] = None,
        check_status_callback: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Gère l'upload complet d'un fichier (Simple ou Multipart).
        
        Args:
            file_path: Chemin absolu du fichier local.
            workspace_id: ID du workspace cible.
            relative_path: Chemin relatif sur Drime (ex: "dossier/fichier.ext").
            progress_callback: Fonction(bytes_transferred) appelée après chaque chunk.
            check_status_callback: Fonction() -> bool. Retourne False si l'action doit être annulée.
                                   Peut bloquer (time.sleep) si en pause.
        
        Returns:
            Dict de l'entrée fichier créée, ou lève une exception.
        """
        file_name = Path(relative_path).name
        file_size = os.path.getsize(file_path)
        
                                 
        MULTIPART_THRESHOLD = 30 * 1024 * 1024
        
        if file_size <= MULTIPART_THRESHOLD:
                           
            resp = self.upload_simple(file_path, workspace_id, relative_path, custom_file_name=file_name)
            self._handle_response(resp)                                       
            
                                                       
                                                                                          
            data = resp.json()
            if progress_callback: progress_callback(file_size)
            return self._parse_file_entry(data)

        else:
                              
            return self._upload_multipart_logic(file_path, file_size, relative_path, workspace_id, progress_callback, check_status_callback)

    def _parse_file_entry(self, data: Any) -> Dict[str, Any]:
        """Helper pour extraire l'objet fileEntry de diverses réponses API."""
        if isinstance(data, dict):
            if 'fileEntry' in data: return data['fileEntry']
            if 'id' in data: return data               
        return data

    def _upload_multipart_logic(
        self,
        file_path: str,
        file_size: int,
        relative_path: str,
        workspace_id: str,
        progress_callback: Optional[Callable[[int], None]],
        check_status_callback: Optional[Callable[[], bool]]
    ) -> Dict[str, Any]:
        """Logique interne Multipart (S3)."""
        file_name = Path(relative_path).name
        num_parts = math.ceil(file_size / CHUNK_SIZE)
        
                 
        init_resp = self.upload_multipart_init(file_name, file_size, relative_path, workspace_id)
        self._handle_response(init_resp)
        init_data = init_resp.json()
        upload_id = init_data['uploadId']
        key = init_data['key']
        
        uploaded_parts = []
        bytes_transferred = 0
        
        with open(file_path, "rb") as f:
            part_number = 1
            while part_number <= num_parts:
                                    
                if check_status_callback:
                    if not check_status_callback(): raise DrimeClientError("Annulation utilisateur.")
                
                batch_end = min(part_number + BATCH_SIZE - 1, num_parts)
                batch_nums = list(range(part_number, batch_end + 1))
                
                               
                sign_resp = self.upload_multipart_sign_batch(key, upload_id, batch_nums)
                self._handle_response(sign_resp)
                sign_data = sign_resp.json()
                urls_map = {u['partNumber']: u['url'] for u in sign_data['urls']}
                
                                  
                for pn in batch_nums:
                    if check_status_callback and not check_status_callback(): raise DrimeClientError("Annulation utilisateur.")
                    
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    
                    url = urls_map.get(pn)
                    if not url: raise DrimeServerError(f"URL manquante pour part {pn}")
                    
                                          
                    for attempt in range(PART_UPLOAD_RETRIES):
                        try:
                            r = self.upload_multipart_put_chunk(url, chunk)
                            if r.status_code in [200, 201]:
                                uploaded_parts.append({"PartNumber": pn, "ETag": r.headers.get("ETag", "").strip('"')})
                                bytes_transferred += len(chunk)
                                if progress_callback: progress_callback(len(chunk))
                                break          
                            else:
                                if attempt == PART_UPLOAD_RETRIES - 1:
                                    raise DrimeNetworkError(f"Échec upload chunk {pn}: {r.status_code}")
                                time.sleep(1 * (attempt + 1))
                        except Exception as e:
                             if attempt == PART_UPLOAD_RETRIES - 1: raise e
                             time.sleep(1 * (attempt + 1))
                    
                part_number += BATCH_SIZE
        
                     
        comp_resp = self.upload_multipart_complete(key, upload_id, uploaded_parts)
        self._handle_response(comp_resp)
        
        comp_data = comp_resp.json()
        if 'fileEntry' in comp_data or ('id' in comp_data and 'name' in comp_data):
             return self._parse_file_entry(comp_data)

        ext = Path(file_name).suffix.lstrip('.')
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        
        entry_data = {
            "clientMime": mime_type, 
            "clientName": file_name,
            "filename": key.split("/")[-1], 
            "size": file_size, 
            "clientExtension": ext,
            "relativePath": relative_path, 
            "workspaceId": workspace_id
        }
        
        entry_resp = self.create_entry(entry_data)
        self._handle_response(entry_resp)
        
        return self._parse_file_entry(entry_resp.json())

    def list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Liste les fichiers et dossiers d'un workspace.
        Supporte la pagination et le filtrage (deletedOnly, folderId).
        """
        return self.request_json('GET', '/drive/file-entries', params=params)

    def get_file_entry(self, entry_id: str) -> requests.Response:
        """Récupère les métadonnées détaillées d'un fichier spécifique."""
        return self.session.get(
            f"{self.api_base_url}/drive/file-entries/{entry_id}",
            timeout=HTTP_TIMEOUT
        )

    def get_download_stream(self, url: str) -> requests.Response:
        """
        Initie un téléchargement en mode streaming.
        Gère manuellement la redirection pour NE PAS envoyer le header Authorization au serveur de stockage (S3).
        """
        r = self.session.get(url, stream=True, allow_redirects=False, timeout=HTTP_TIMEOUT)
        
        if r.status_code in [301, 302, 303, 307, 308] and 'Location' in r.headers:
            redirect_url = r.headers['Location']
            r.close()                                 
            
            s3_headers = {
                "Authorization": None,                                                      
                "User-Agent": self.headers.get("User-Agent"),
                "Accept": "*/*"
            }
            
            return self.session.get(redirect_url, headers=s3_headers, stream=True, timeout=HTTP_TIMEOUT)
            
        return r

    def download_file(self, url: str, dest_path: str) -> bool:
        """
        Télécharge un fichier complet vers le disque local.
        Gère le streaming pour éviter de charger tout le fichier en RAM.
        """
        try:
            with self.session.get(url, stream=True, timeout=HTTP_TIMEOUT * 2) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"[API] Erreur download_file: {e}")
            return False

    def delete_entries(self, entry_ids: List[str], delete_forever: bool = False, **kwargs) -> Dict[str, Any]:
        """Supprime (soft delete) ou détruit définitivement des fichiers/dossiers."""
        return self.request_json('POST', '/file-entries/delete', json={"entryIds": entry_ids, "deleteForever": delete_forever}, **kwargs)

    def rename_entry(self, entry_id: str, new_name: str) -> Dict[str, Any]:
        """Renomme un fichier ou un dossier."""
        return self.request_json('PUT', f"/file-entries/{entry_id}", json={"name": new_name})

    def create_folder(self, name: str, parent_id: Optional[str], workspace_id: str) -> Dict[str, Any]:
        """Crée un nouveau dossier dans l'arborescence."""
        return self.request_json('POST', '/folders', json={"name": name, "parentId": parent_id, "workspaceId": workspace_id})

    def upload_simple_bytes(self, file_content: bytes, file_name: str, workspace_id: str, relative_path: str, mime_type: str = "application/octet-stream") -> requests.Response:
        """
        Upload simple à partir de données en mémoire (bytes).
        Utile pour les petits fichiers générés à la volée (ex: fichiers de configuration).
        """
                                                                                                                    
        return self.session.post(
            f"{self.api_base_url}/uploads",
            files={"file": (file_name, file_content, mime_type)},
            data={"relativePath": relative_path, "workspaceId": workspace_id},
            timeout=HTTP_TIMEOUT * 2
        )

    def restore_entry(self, entry_ids: List[str]) -> Dict[str, Any]:
        """Restaure des éléments depuis la corbeille."""
        return self.request_json('POST', '/file-entries/restore', json={"entryIds": entry_ids})

    def empty_trash(self, workspace_id: str) -> Dict[str, Any]:
        """Vide définitivement la corbeille d'un workspace."""
        return self.request_json('POST', '/file-entries/empty-trash', json={"workspaceId": workspace_id})

    def create_share_link(self, entry_id: str, password: Optional[str] = None, expires_at: Optional[str] = None, 
                          allow_edit: bool = False, allow_download: bool = True, notify_on_download: bool = False) -> requests.Response:
        """
        Crée un lien de partage public pour un fichier ou dossier.
        """
        payload = {
            "password": password,
            "expiresAt": expires_at,
            "allowEdit": allow_edit,
            "allowDownload": allow_download,
            "notifyOnDownload": notify_on_download
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        return self.session.post(
            f"{self.api_base_url}/file-entries/{entry_id}/shareable-link",
            json=payload,
            timeout=HTTP_TIMEOUT
        )