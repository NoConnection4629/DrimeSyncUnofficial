import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, BOLD, LEFT
import io
import os
import math
import secrets
import uuid
import json
import hashlib
import threading
from datetime import datetime
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
except ImportError as e:
    print(f"Erreur Import PIL/QR : {e}")
    qrcode = None

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    print("Info: Support HEIC (pillow-heif) non disponible.")
try:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader
except ImportError:
    print("Erreur Import PDF - Vérifiez les dépendances")
import tempfile
from io import BytesIO
from drimesyncunofficial.constants import (
    COL_VERT, COL_GRIS, COL_TEXT_GRIS, COL_JAUNE, COL_ROUGE, COL_VIOLET, COL_BLEU, COL_BLEU2, 
    API_BASE_URL, HTTP_TIMEOUT, MODE_NO_ENC, CONF_KEY_API_KEY, CONF_KEY_ENCRYPTION_MODE, 
    CONF_KEY_E2EE_PASSWORD, ANDROID_DOWNLOAD_PATH
)
from typing import Optional
from drimesyncunofficial.utils import generate_or_load_salt, derive_key, E2EE_encrypt_file, format_size
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.ui_thread_utils import safe_update_label, safe_log, run_in_background
from drimesyncunofficial.about_filigranage import AboutFiligranageManager
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.filigranage_engine import OmegaEngine
from drimesyncunofficial.i18n import tr

MULTIPART_THRESHOLD = 30 * 1024 * 1024
CHUNK_SIZE = 25 * 1024 * 1024
BATCH_SIZE = 10

class WatermarkManager(LoggerMixin):
    def __init__(self, app):
        self.app = app
        self.window = None
        self.engine = OmegaEngine(log_callback=self._engine_log_adapter)
        self.org_input = None
        self.motif_input = None
        self.log_label = None
        self.lbl_conflict_warning = None
        self.chk_crypto_link = None
        self.chk_microprint = None
        self.chk_mesh = None
        self.chk_anti_copy = None
        self.chk_qr_triangulation = None
        self.chk_parano = None
        self.chk_encrypt = None
        self.main_box_content = None
    def show_about_window(self, widget=None):
        self.about_manager = AboutFiligranageManager(self.app)
        self.about_manager.show()

    def action_show_meta(self, widget):
        from drimesyncunofficial.filigranage_meta import MetadataReaderManager
        MetadataReaderManager(self.app).show()

    def show(self):
        main_box = toga.Box(style=Pack(direction=COLUMN))
        nav_box = toga.Box(style=Pack(direction=ROW, margin=10, align_items=CENTER))
        btn_back = create_back_button(self.app.retour_arriere, margin_bottom=0)
        btn_meta = toga.Button(tr("btn_metadata", "🔍 Métadonnées"), on_press=self.action_show_meta, style=Pack(margin_right=5))
        btn_notice = toga.Button(tr("btn_help", "ℹ️ Aide"), on_press=self.show_about_window, style=Pack(background_color=COL_BLEU2, color='white'))
        nav_box.add(btn_back)
        nav_box.add(toga.Box(style=Pack(flex=1))) 
        nav_box.add(btn_meta)
        nav_box.add(btn_notice)
        main_box.add(nav_box)
        header = toga.Box(style=Pack(direction=COLUMN, margin_bottom=5, margin_left=20))
        header.add(toga.Label("--- FILIGRANAGE SÉCURISÉ ---", style=Pack(font_size=12, font_weight=BOLD, color=COL_BLEU2, text_align=LEFT, margin_bottom=2)))
        header.add(toga.Label("Sécurité Forensique", style=Pack(font_size=10, color=COL_TEXT_GRIS, text_align=LEFT, margin_bottom=5)))
        main_box.add(header)
        form_card = toga.Box(style=Pack(direction=COLUMN, margin=5))
        lbl_style = Pack(color=COL_TEXT_GRIS, font_size=12, font_weight=BOLD, margin_bottom=5, text_align=LEFT)
        input_style = Pack(color=COL_TEXT_GRIS, font_size=12, margin=8, flex=1)
        row_style = Pack(direction=COLUMN, margin_bottom=15)
        box_org = toga.Box(style=row_style)
        box_org = toga.Box(style=row_style)
        box_org.add(toga.Label(tr("watermark_org_label", "Organisme Destinataire"), style=lbl_style))
        self.org_input = toga.TextInput(placeholder=tr("watermark_org_ph", "ex: Banque, Notaire..."), style=input_style)
        box_org.add(self.org_input)
        box_motif = toga.Box(style=row_style)
        box_motif.add(toga.Label(tr("watermark_motif_label", "Motif de l'envoi"), style=lbl_style))
        self.motif_input = toga.TextInput(placeholder=tr("watermark_motif_ph", "ex: Dossier location"), style=input_style)
        box_motif.add(self.motif_input)
        box_auth = toga.Box(style=row_style)
        box_auth.add(toga.Label(tr("watermark_auth_label", "Auteur / Copy. (Optionnel)"), style=lbl_style))
        self.auth_input = toga.TextInput(placeholder=tr("watermark_auth_ph", "Votre Nom ou Organisation"), style=input_style)
        box_auth.add(self.auth_input)
        box_ws = toga.Box(style=Pack(direction=COLUMN, margin_bottom=5))
        box_ws.add(toga.Label(tr("watermark_dest_label", "Destination"), style=lbl_style))
        ws_items = [tr("watermark_mode_local", "Mode Local (même dossier)"), "Espace Personnel (ID: 0)"]
        if hasattr(self.app, 'workspace_list_cache') and self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache:
                ws_items.append(f"{ws.get('name', 'Inconnu')} (ID: {ws.get('id', '?')})")
        self.ws_input = toga.Selection(items=ws_items, style=input_style, on_change=self.on_ws_change)
        box_ws.add(self.ws_input)
        self.lbl_conflict_warning = toga.Label(
            tr("watermark_warning_conflict", "❌ CONFLIT : Workspace utilisé par un miroir.\nRisque de désynchronisation."),
            style=Pack(width=310, font_size=7, color=COL_ROUGE, font_weight=BOLD, margin_bottom=10, visibility='hidden')
        )
        form_card.add(box_org)
        form_card.add(box_motif)
        form_card.add(box_auth)
        form_card.add(box_ws)
        form_card.add(self.lbl_conflict_warning)
        form_card.add(toga.Label(tr("watermark_sec_options", "Options de Sécurité :"), style=Pack(font_weight=BOLD, margin_bottom=5, font_size=10)))
        security_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        col_left = toga.Box(style=Pack(direction=COLUMN, flex=1, padding_right=5))
        self.chk_crypto_link = toga.Switch(tr("watermark_opt_link", "Liaison Cryptographique"), value=True, on_change=self.on_crypto_link_change, style=Pack(margin_bottom=5))
        self.chk_qr_triangulation = toga.Switch(tr("watermark_opt_qr", "Triangulation QR"), value=False, style=Pack(margin_bottom=5))
        self.chk_encrypt = toga.Switch(tr("watermark_opt_enc", "Chiffrement E2EE (Upload)"), value=False, style=Pack(margin_bottom=5))
        self.chk_encrypt.enabled = False 
        col_left.add(self.chk_crypto_link)
        col_left.add(self.chk_qr_triangulation)
        col_left.add(self.chk_encrypt)
        col_right = toga.Box(style=Pack(direction=COLUMN, flex=1, padding_left=5))
        self.chk_microprint = toga.Switch(tr("watermark_opt_micro", "Bordures Microprint"), value=True, style=Pack(margin_bottom=5))
        self.chk_anti_copy = toga.Switch(tr("watermark_opt_anticopy", "Protection Anti-Photocopie"), value=False, style=Pack(margin_bottom=5))
        self.chk_parano = toga.Switch(tr("watermark_opt_pdf_enc", "Chiffrement PDF (MDP)"), value=False, on_change=self.on_parano_change, style=Pack(margin_bottom=5))
        self.pwd_input = toga.TextInput(placeholder=tr("watermark_pdf_pwd_ph", "Mot de passe PDF"), style=Pack(margin_bottom=5, visibility='hidden'))
        col_right.add(self.chk_microprint)
        col_right.add(self.chk_anti_copy)
        col_right.add(self.chk_parano)
        col_right.add(self.pwd_input)
        security_box.add(col_left)
        security_box.add(col_right)
        form_card.add(security_box)
        self.log_label = toga.Label(tr("init_ready", "Système prêt."), style=Pack(color=COL_BLEU2, font_size=10, margin_bottom=0, text_align=CENTER))
        form_card.add(self.log_label)
        btn = toga.Button(tr("btn_secure_doc", "🔒 SÉCURISER LE DOCUMENT"), on_press=self.run_omega, style=Pack(background_color=COL_BLEU2, color='white', font_weight=BOLD, font_size=13, height=45, margin_top=0, margin_bottom=2))
        form_card.add(btn)
        form_card.add(toga.Label("Log :", style=Pack(font_weight=BOLD, margin_top=2, margin_bottom=0, font_size=10)))
        self.txt_logs = create_logs_box(height=150, margin=5)
        form_card.add(self.txt_logs)
        scroll_container = toga.ScrollContainer(content=form_card, style=Pack(margin=5, flex=1))
        main_box.add(scroll_container)
        self.main_box_content = main_box 
        self.app.changer_ecran(main_box)
    def _engine_log_adapter(self, message, color=None):
        self.log_ui(message, color)

    def log_ui(self, message: str, color: Optional[str] = None, debug: bool = False) -> None:
        super().log_ui(message, color, debug)
        
        if self.log_label:
            txt = str(message).split('\n')[0]
            style = {'color': color} if color else None
            safe_update_label(self.app, self.log_label, txt, style)
    def on_ws_change(self, widget):
        self.update_warnings(widget)
        val = self.ws_input.value
        if "Mode Local" in val:
            self.chk_encrypt.value = False
            self.chk_encrypt.enabled = False
        else:
            self.chk_encrypt.enabled = True
    def _get_selected_workspace_id(self):
        val = self.ws_input.value
        if not val or "Mode Local" in val: return None
        try: return val.split("(ID: ")[1].replace(")", "")
        except: return None
    def _get_ws_name_from_id(self, ws_id):
        if ws_id == '0':
            return "Espace Personnel (ID: 0)"
        if hasattr(self.app, 'workspace_list_cache') and self.app.workspace_list_cache:
            for ws in self.app.workspace_list_cache:
                if str(ws.get('id')) == ws_id:
                    return f"{ws.get('name')} (ID: {ws_id})"
        return f"ID Inconnu ({ws_id})"
    def update_warnings(self, widget):
        if not self.lbl_conflict_warning: return
        selected_id = self._get_selected_workspace_id()
        if not selected_id:
            self.lbl_conflict_warning.style.visibility = 'hidden'
            return
        ws_standard_id = self.app.config_data.get('workspace_standard_id', '0')
        ws_e2ee_id = self.app.config_data.get('workspace_e2ee_id', '0')
        is_conflict = False
        conflict_mode = None
        conflict_id = None
        if selected_id == ws_standard_id:
            is_conflict = True
            conflict_mode = "Miroir STANDARD"
            conflict_id = ws_standard_id
        elif selected_id == ws_e2ee_id:
            is_conflict = True
            conflict_mode = "Miroir CHIFFRÉ (E2EE)"
            conflict_id = ws_e2ee_id
        if is_conflict:
            conflict_ws_name = self._get_ws_name_from_id(conflict_id)
            self.lbl_conflict_warning.text = (
                f"❌ CONFLIT : Workspace '{conflict_ws_name}'\nUtilisé par {conflict_mode}. Risque de désynchronisation."
            )
            self.lbl_conflict_warning.style.visibility = 'visible'
        else:
            self.lbl_conflict_warning.style.visibility = 'hidden'
    async def on_crypto_link_change(self, widget):
        if not self.chk_crypto_link.value:
            self.chk_crypto_link.value = True
            await self.app.main_window.dialog(toga.InfoDialog("Protection Minimale", "La liaison cryptographique est la protection minimale requise et ne peut pas être désactivée."))
    def on_parano_change(self, widget):
        if self.chk_parano.value:
            self.pwd_input.style.visibility = 'visible'
        else:
            self.pwd_input.style.visibility = 'hidden'
            self.pwd_input.value = ""
    def show_about_window(self, widget):
        AboutFiligranageManager(self.app).show()
    def get_selected_ws_id(self):
        val = self.ws_input.value
        if "Mode Local" in val: return None
        try:
            return val.split("(ID: ")[1].replace(")", "")
        except:
            return None
    def calculate_file_hash(self, filepath):
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    async def get_secure_payload(self, file_hash):
        org = self.org_input.value
        if not org:
            await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Destinataire requis."))
            return None
        uid = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        author = self.auth_input.value.strip() or "DrimeSync Unofficial"
        user_pwd = None
        if self.chk_parano.value:
            user_pwd = self.pwd_input.value
            if not user_pwd:
                await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Mot de passe PDF requis en mode Parano."))
                return None
        return {
            "to": org.upper(),
            "doc_hash": file_hash[:16],
            "ts": timestamp,
            "uuid": uid,
            "sec": "SHA256+HQ",
            "author": author,
            "user_pwd": user_pwd
        }
    def run_omega(self, widget):
        if self.chk_parano.value:
            valid_exts = ['.pdf']
            ftypes_desktop = ["pdf"]
        else:
            valid_exts = ['.pdf', '.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.tiff', '.tif']
            ftypes_desktop = ["pdf", "jpg", "jpeg", "png", "heic", "webp", "bmp", "tiff", "tif"]
        if self.app.is_mobile:
            def on_file_picked(result_paths):
                self.app.main_window.content = self.main_box_content
                if result_paths:
                    fname_str = str(result_paths[0])
                    self.app.loop.create_task(self._continue_omega_process(fname_str))
                else:
                    self.log_ui("Sélection annulée.", COL_JAUNE)
            browser = AndroidFileBrowser(self.app, on_file_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=False, valid_extensions=valid_exts)
            self.app.main_window.content = browser
        else:
            async def _ask_file_desktop():
                fname = await self.app.main_window.dialog(toga.OpenFileDialog(
                    title="Fichier Source",
                    multiple_select=False,
                    file_types=ftypes_desktop
                ))
                if fname:
                    await self._continue_omega_process(str(fname))
            self.app.loop.create_task(_ask_file_desktop())
    async def _continue_omega_process(self, fname_str):
        """Suite du processus une fois le fichier sélectionné (Mobile ou Desktop)"""
        try:
            ext = fname_str.lower().split('.')[-1]
            if ext != 'pdf':
                self.chk_parano.value = False
                self.chk_parano.enabled = False
                self.pwd_input.style.visibility = 'hidden'
                self.pwd_input.value = ""
                self.log_ui("ℹ️ Mode Parano désactivé (PDF uniquement)", COL_GRIS)
            else:
                self.chk_parano.enabled = True
            self.log_ui("Hashage du fichier original...")
            loop = asyncio.get_running_loop()
            file_hash = await loop.run_in_executor(None, self.calculate_file_hash, fname_str)
            data = await self.get_secure_payload(file_hash)
            if data:
                options = {
                    "crypto_link": self.chk_crypto_link.value,
                    "microprint": self.chk_microprint.value,
                    "mesh": self.chk_crypto_link.value, 
                    "anti_copy": self.chk_anti_copy.value,
                    "qr_triangulation": self.chk_qr_triangulation.value,
                    "chk_encrypt": self.chk_encrypt.value,                          
                    "ws_id": self._get_selected_workspace_id()                          
                }
                self.log_ui("Application des calques...")
                                                                                                      
                run_in_background(self.process_file, fname_str, data, options)
        except Exception as e:
            await self.app.main_window.dialog(toga.ErrorDialog("Erreur", str(e)))
    def process_file_sync(self, fpath, data, options):
         self.process_file(fpath, data, options)
    
    def process_file(self, fpath, data, options):
                                                                                    
                                                                    
        path_str = str(fpath)
        ext = path_str.lower().split('.')[-1]
        if ext == 'pdf':
            out_path = path_str.replace(f".{ext}", "_SECURE.pdf")
        else:
            out_path = path_str.rsplit('.', 1)[0] + "_SECURE.jpg"
        try:
            self.log_ui(f"[DEBUG] Génération QR Code pour {data['doc_hash'][:8]}...")
                                   
            qr_img = self.engine.generate_qr_code(data)
            
            if ext == 'pdf':
                self.log_ui("[DEBUG] Moteur PDF (Engine) activé...")
                self.engine.process_pdf(path_str, out_path, data, qr_img, options)
            else:
                self.log_ui("[DEBUG] Moteur Image (Engine) activé...")
                self.engine.process_image(path_str, out_path, data, qr_img, options)
            print("[DEBUG_CONSOLE] Engine finished.")
            if not os.path.exists(out_path):
                raise Exception(f"Le fichier de sortie n'a pas été créé : {out_path}")
            print("[DEBUG_CONSOLE] Output file verified.")
            self.log_ui(f"Fichier sauvegardé : {out_path}", COL_VERT)
            final_path = out_path
            
                                                   
            if options.get("chk_encrypt"):
                self.log_ui("Préparation chiffrement upload...", COL_JAUNE)
                e2ee_mode = self.app.config_data.get(CONF_KEY_ENCRYPTION_MODE, MODE_NO_ENC)
                e2ee_pass = self.app.config_data.get(CONF_KEY_E2EE_PASSWORD, '')
                if e2ee_mode == MODE_NO_ENC:
                    self.log_ui("⚠️ Chiffrement demandé mais désactivé dans Config !", COL_ROUGE)
                    def _warn_enc():
                        self.app.main_window.dialog(toga.InfoDialog("Attention", "Vous avez demandé le chiffrement mais le mode est 'Non Chiffré' dans les paramètres.\n\nLe fichier reste en CLAIR."))
                    self.app.loop.call_soon_threadsafe(_warn_enc)
                elif not e2ee_pass:
                    self.log_ui("⚠️ Mot de passe E2EE manquant !", COL_ROUGE)
                    def _warn_pass():
                        self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Mot de passe de chiffrement non configuré."))
                    self.app.loop.call_soon_threadsafe(_warn_pass)
                else:
                    try:
                        salt = generate_or_load_salt(self.app.paths)
                        if not salt: raise Exception("Impossible de charger le sel")
                        key = derive_key(str(e2ee_pass), salt)
                        self.log_ui(f"Chiffrement ({e2ee_mode})...")
                        encrypted_data = E2EE_encrypt_file(out_path, key)
                        enc_path = out_path + ".enc"
                        with open(enc_path, 'wb') as f:
                            f.write(encrypted_data)
                        self.log_ui(f"Fichier CHIFFRÉ généré : {enc_path}", COL_VIOLET)
                        final_path = f"{out_path}\n+ {enc_path}"
                    except Exception as e:
                        self.log_ui(f"Erreur Chiffrement: {e}", COL_ROUGE)
            
                                                          
            ws_id = options.get("ws_id")
            if ws_id:
                file_to_upload = out_path
                                              
                if options.get("chk_encrypt") and os.path.exists(out_path + ".enc"):
                    file_to_upload = out_path + ".enc"
                self.log_ui(f"Début Upload vers Workspace {ws_id}...", COL_BLEU)
                if self.upload_file(file_to_upload, ws_id):
                    final_path += "\n\n✅ UPLOAD RÉUSSI"
                else:
                    final_path += "\n\n❌ ÉCHEC UPLOAD"
            
                                  
            async def show_success_dialog():
                await self.app.main_window.dialog(toga.InfoDialog("Fichier Sécurisé", f"Sauvegardé sous :\n{final_path}"))
            asyncio.run_coroutine_threadsafe(show_success_dialog(), self.app.loop)
        
        except Exception as e:
            print(f"[DEBUG_CONSOLE] EXCEPTION IN THREAD: {e}")
            import traceback
            traceback.print_exc()
            err_msg = str(e)
            self.log_ui(f"ERREUR: {err_msg}", COL_ROUGE)
            async def show_error_dialog():
                await self.app.main_window.dialog(toga.ErrorDialog("Erreur Traitement", err_msg))
            asyncio.run_coroutine_threadsafe(show_error_dialog(), self.app.loop)
        
        print("[DEBUG_CONSOLE] THREAD EXITING.")
                                                             
                                                                                          
    def upload_file(self, file_path, workspace_id):
        """
        Refactorisé Task 24 : Utilise le client API centralisé.
        Gère automatiquement Simple vs Multipart via api_client.upload_file.
        """
        try:
            self.log_ui(f"Début Upload vers Workspace {workspace_id}...", COL_BLEU)
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            def progress_cb(transferred):
                if file_size > 0:
                    pct = (transferred / file_size) * 100
                    self.log_ui(f"Upload : {pct:.1f}%", COL_BLEU2)

            resp_dict = self.app.api_client.upload_file(
                file_path=str(file_path),
                workspace_id=str(workspace_id),
                relative_path=file_name,
                progress_callback=progress_cb
            )

            if resp_dict and resp_dict.get('id'):
                self.log_ui("Upload Réussi !", COL_VERT)
                return True
            else:
                self.log_ui("Upload terminé mais ID manquant (bizarre).", COL_ROUGE)
                return False

        except Exception as e:
            self.log_ui(f"Erreur Upload Centralisé : {e}", COL_ROUGE)
            return False