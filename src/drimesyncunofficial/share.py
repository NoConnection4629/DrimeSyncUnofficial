import toga
import asyncio
import os
import re
import math
import mimetypes
import shutil                                      
import json
from pathlib import Path
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD
from drimesyncunofficial.constants import (
    COL_JAUNE, COL_ROUGE, COL_VERT, COL_VIOLET2, COL_GRIS, 
    COL_BLEU, COL_ORANGE, COL_TEXT_GRIS, COL_BLEU2, CONF_KEY_DEBUG_MODE, COL_VIOLET, CONF_KEY_API_KEY
)
from drimesyncunofficial.browsers import AndroidFileBrowser
from drimesyncunofficial.capsule_manager import CapsuleManager
from drimesyncunofficial.mixins import LoggerMixin
from drimesyncunofficial.ui_utils import create_back_button, create_logs_box
from drimesyncunofficial.utils import make_zip, get_total_size, validate_password_compliance
from drimesyncunofficial.about_share import AboutShareManager
from drimesyncunofficial.i18n import tr

NON_EDITABLE_EXTENSIONS = {
    'htm', 'html', '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lz', '.zst',
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp',
    '.mp3', '.wav', '.aac', '.flac', '.ogg', '.wma', '.m4a', '.opus',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.heic',
    '.exe', '.msi', '.iso', '.bin', '.dll', '.sys',
    '.apk', '.aab', '.obb',
    '.dmg', '.pkg', '.ipa', '.plist', '.dylib',
    '.deb', '.rpm', '.appimage', '.snap', '.flatpak', '.so', '.ko', '.sh', '.run'
}


class ShareManager(LoggerMixin):
    def __init__(self, app):
        self.app = app
        self.window = None
        self.selected_file_path = None
        self.about_share_manager = AboutShareManager(app)

    def show(self):
        if not self.app.config_data.get(CONF_KEY_API_KEY):
            self.app.loop.create_task(self.app.main_window.dialog(toga.InfoDialog("Erreur", "Veuillez configurer la clé API.")))
            return
        main_container = toga.ScrollContainer(horizontal=False)
        
        box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        
        header_box = toga.Box(style=Pack(direction=ROW, margin_bottom=15, align_items='center'))
        header_box.add(create_back_button(self.app.retour_arriere, width=100, margin_bottom=0))
        
        header_box.add(toga.Box(style=Pack(flex=1)))
        
        btn_info = toga.Button(tr("btn_how_it_works", "ℹ️ Comment ça marche ?"), on_press=lambda w: self.about_share_manager.show(), style=Pack(background_color=COL_BLEU2, color='white'))
        header_box.add(btn_info)
        
        box.add(header_box)

        box.add(toga.Label(tr("share_title", "--- PARTAGE DE FICHIERS ---"), style=Pack(font_weight=BOLD, font_size=12, margin_bottom=20, color=COL_VIOLET2)))
        
        file_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=20))
        file_box.add(toga.Label(tr("share_file_label", "Fichier à partager :"), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        self.lbl_file_path = toga.Label(tr("share_no_file", "Aucun fichier sélectionné"), style=Pack(margin_bottom=5, font_size=8, color='gray'))
        file_box.add(self.lbl_file_path)
        
        if self.app.is_mobile:
            row_btns = toga.Box(style=Pack(direction=ROW))
            btn_file = toga.Button(tr("btn_file", "📄 Fichier"), on_press=self.action_select_file, style=Pack(flex=1, margin_right=5))
            btn_folder = toga.Button(tr("btn_folder", "📂 Dossier"), on_press=self.action_select_folder, style=Pack(flex=1, margin_left=5))
            row_btns.add(btn_file)
            row_btns.add(btn_folder)
            file_box.add(row_btns)
        else:
            row_btns = toga.Box(style=Pack(direction=ROW))
            btn_file = toga.Button(tr("btn_file", "📄 Fichier"), on_press=self.action_select_file_desktop, style=Pack(flex=1, margin_right=5))
            btn_folder = toga.Button(tr("btn_folder", "📂 Dossier"), on_press=self.action_select_folder_desktop, style=Pack(flex=1, margin_left=5))
            row_btns.add(btn_file)
            row_btns.add(btn_folder)
            file_box.add(row_btns)
            
        box.add(file_box)
        
        box.add(toga.Divider(style=Pack(margin_bottom=10)))

        security_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        security_box.add(toga.Label(tr("share_mode_label", "Mode de Partage : "), style=Pack(font_weight=BOLD, margin_bottom=5)))
        
        self.switch_secure = toga.Switch(tr("share_switch_zk", "Capsule Sécurisée (E2EE - Zero-Knowledge - 150 Mo max)"), on_change=self.on_security_toggle)
        security_box.add(self.switch_secure)
        
        box.add(security_box)
        
        
        self.box_standard_warning = toga.Box(style=Pack(direction=COLUMN, margin_bottom=20))
        warn_std_text = tr("share_warn_std", "⚠️ STANDARD (Lien Cloud) :\nGénère un lien public Drime. \nAttention : Données stockées sur le cloud/serveur.")
        self.box_standard_warning.add(toga.Label(warn_std_text, style=Pack(color=COL_ROUGE, font_weight=BOLD, font_size=9, margin_bottom=10)))
        
        box.add(self.box_standard_warning)                      

        self.box_secure_inputs = toga.Box(style=Pack(direction=COLUMN, margin_bottom=20))
        warn_sec_text = tr("share_warn_sec", "🔒 CAPSULE ZERO-KNOWLEDGE :\nCrée un fichier HTML chiffré autonome.\nLe fichier sera indéchiffrable sans le Mot de passe ET le Token.")
        self.box_secure_inputs.add(toga.Label(warn_sec_text, style=Pack(color=COL_VERT, font_weight=BOLD, font_size=9, margin_bottom=10)))
        
        self.box_secure_inputs.add(toga.Label(tr("share_pwd_label", "Mot de passe de déchiffrement (Capsule) :"), style=Pack(font_size=8)))
        
        initial_pwd_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        
        self.input_password = toga.PasswordInput(placeholder=tr("share_pwd_placeholder", "Mot de passe fort requis"), style=Pack(flex=1))
        initial_pwd_box.add(self.input_password)
        
        self.btn_show_pwd = toga.Button("👁️", on_press=self.toggle_password_visibility, style=Pack(width=40, margin_left=5))
        initial_pwd_box.add(self.btn_show_pwd)
        
        self.box_secure_inputs.add(initial_pwd_box)
        self.pwd_container = initial_pwd_box                               
        self.is_pwd_visible = False
        
        self.box_secure_inputs.add(toga.Label(tr("share_token_label", "Token de Sécurité (Généré après création) :"), style=Pack(font_size=8, font_weight=BOLD)))
        self.input_salt = toga.TextInput(readonly=True, placeholder=tr("share_token_placeholder", "Le Token apparaîtra ici..."), style=Pack(margin_bottom=10, background_color=COL_GRIS, color='black', font_weight=BOLD))
        self.box_secure_inputs.add(self.input_salt)

        box.add(toga.Divider(style=Pack(margin_bottom=10)))
        box.add(toga.Label(tr("share_options_title", "Options du Lien de Partage :"), style=Pack(font_weight=BOLD, margin_bottom=10)))
        
        options_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))
        
        row_opt_1 = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        
        self.chk_download = toga.Switch(tr("share_opt_download", "Autoriser le téléchargement"), on_change=None, value=True, style=Pack(flex=1, margin_right=5))
        row_opt_1.add(self.chk_download)
        
        self.chk_expiration = toga.Switch(tr("share_opt_expiry", "Date d'expiration du lien"), on_change=self.on_expiration_toggle, style=Pack(flex=1, margin_left=5))
        row_opt_1.add(self.chk_expiration)
        
        options_box.add(row_opt_1)
        
        self.container_expiration = toga.Box(style=Pack(direction=COLUMN, margin_bottom=5))
        self.input_date = toga.DateInput(style=Pack(margin_bottom=10))
        options_box.add(self.container_expiration)

        row_opt_2 = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        
        self.chk_link_pwd = toga.Switch(tr("share_opt_pwd", "Mot de passe du lien (serveur)"), on_change=self.on_link_pwd_toggle, style=Pack(flex=1, margin_right=5))
        row_opt_2.add(self.chk_link_pwd)
        
        
        self.chk_notify = toga.Switch(tr("share_opt_notify", "Suivi des téléchargements"), style=Pack(flex=1, margin_left=5))
        row_opt_2.add(self.chk_notify)
        
        options_box.add(row_opt_2)

        self.container_link_pwd = toga.Box(style=Pack(direction=COLUMN, margin_bottom=5))
        
        self.box_link_pwd_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        self.input_link_pwd = toga.PasswordInput(placeholder=tr("share_link_pwd_placeholder", "Mot de passe du lien (Serveur)"), style=Pack(flex=1))
        self.btn_show_link_pwd = toga.Button("👁️", on_press=self.toggle_link_pwd_visibility, style=Pack(width=40, margin_left=5))
        self.box_link_pwd_row.add(self.input_link_pwd)
        self.box_link_pwd_row.add(self.btn_show_link_pwd)
        
        self.is_link_pwd_visible = False
        self.container_link_pwd.add(self.box_link_pwd_row)
        
        options_box.add(self.container_link_pwd)

        self.chk_edit = toga.Switch(tr("share_opt_edit", "Autoriser l'édition du fichier (Office, txt, etc.)"), style=Pack(margin_top=5))
        options_box.add(self.chk_edit)
        
        box.add(options_box)
        
        box.add(toga.Divider(style=Pack(margin_bottom=10)))
        self.btn_share = toga.Button(tr("btn_generate_link", "Générer le lien"), on_press=self.action_generate, style=Pack(background_color=COL_VIOLET2, color='white', font_weight=BOLD, height=45, margin_bottom=20))
        box.add(self.btn_share)

        self.box_result_link = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        self.box_result_link.add(toga.Label(tr("share_result_link", "Lien généré :"), style=Pack(font_weight=BOLD, font_size=9)))
        
        row_link = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.input_std_link = toga.TextInput(readonly=True, placeholder=tr("share_link_placeholder", "Le lien apparaîtra ici..."), style=Pack(color=COL_VIOLET, background_color=COL_GRIS, font_weight=BOLD, flex=1))
        row_link.add(self.input_std_link)
        
        self.box_result_link.add(row_link)
        box.add(self.box_result_link)

        box.add(toga.Label("Log :", style=Pack(font_weight=BOLD, margin_bottom=5, margin_top=10)))
        self.txt_logs = create_logs_box(height=150)
        box.add(self.txt_logs)

        main_container.content = box
        self.content_box = box
        self.app.changer_ecran(main_container)

        self.on_link_pwd_toggle(self.chk_link_pwd)
        self.on_expiration_toggle(self.chk_expiration)

    def on_link_pwd_toggle(self, widget):
        if widget.value:
            if self.box_link_pwd_row not in self.container_link_pwd.children:
                self.container_link_pwd.add(self.box_link_pwd_row)
        else:
            if self.box_link_pwd_row in self.container_link_pwd.children:
                self.container_link_pwd.remove(self.box_link_pwd_row)

    def toggle_link_pwd_visibility(self, widget):
        if not self.box_link_pwd_row: return
        
        current_val = self.input_link_pwd.value
        self.is_link_pwd_visible = not self.is_link_pwd_visible
        
        self.box_link_pwd_row.remove(self.input_link_pwd)
        
        if self.is_link_pwd_visible:
            new_input = toga.TextInput(placeholder=tr("share_link_pwd_placeholder", "Mot de passe du lien (Serveur)"), style=Pack(flex=1))
            widget.text = "🔒"                      
        else:
            new_input = toga.PasswordInput(placeholder=tr("share_link_pwd_placeholder", "Mot de passe du lien (Serveur)"), style=Pack(flex=1))
            widget.text = "👁️"                       
            
        new_input.value = current_val
        self.input_link_pwd = new_input
        self.box_link_pwd_row.insert(0, new_input)
        self.box_link_pwd_row.refresh()



    def on_expiration_toggle(self, widget):
        if widget.value:
            if self.input_date not in self.container_expiration.children:
                self.container_expiration.add(self.input_date)
        else:
            if self.input_date in self.container_expiration.children:
                self.container_expiration.remove(self.input_date)
            

    def on_security_toggle(self, widget):
        is_secure = widget.value
        try:
            if is_secure:
                self.btn_share.text = tr("share_btn_capsule", "💊 Créer la Capsule HTML")
                self.btn_share.style.background_color = COL_VIOLET2
                
                if self.box_standard_warning in self.content_box.children:
                    self.content_box.remove(self.box_standard_warning)
                    
                if self.box_secure_inputs not in self.content_box.children:
                    self.content_box.insert(5, self.box_secure_inputs)
            else:
                self.btn_share.text = tr("share_btn_link", "🔗 Générer le lien Cloud")
                self.btn_share.style.background_color = COL_VIOLET2

                if self.box_secure_inputs in self.content_box.children:
                    self.content_box.remove(self.box_secure_inputs)
                    
                if self.box_standard_warning not in self.content_box.children:
                    self.content_box.insert(5, self.box_standard_warning)
                
                if self.box_result_link not in self.content_box.children:
                    self.content_box.insert(-2, self.box_result_link)
            
            self.content_box.refresh()
        except Exception as e:
            print(f"UI Toggle Error: {e}")

    def toggle_password_visibility(self, widget):
        if not self.pwd_container: return
        
        current_val = self.input_password.value
        self.is_pwd_visible = not self.is_pwd_visible
        
        self.pwd_container.remove(self.input_password)
        
        if self.is_pwd_visible:
            new_input = toga.TextInput(placeholder=tr("share_pwd_placeholder", "Mot de passe fort requis"), style=Pack(flex=1))
            widget.text = "🔒"               
        else:
            new_input = toga.PasswordInput(placeholder=tr("share_pwd_placeholder", "Mot de passe fort requis"), style=Pack(flex=1))
            widget.text = "👁️"               
            
        new_input.value = current_val
        self.input_password = new_input
        self.pwd_container.insert(0, new_input)
        self.pwd_container.refresh()

    def _update_edit_option_state(self):
        """
        Désactive la case 'Autoriser l'édition' pour les dossiers et fichiers non supportés (Vidéos, Zips, etc.)
        """
        if not hasattr(self, 'chk_edit'): return

        disable_edit = False
        path = self.selected_file_path
        
        if not path:
            disable_edit = True
        else:
            path_obj = Path(path)
            if path_obj.is_dir():
                disable_edit = True
            elif path_obj.suffix.lower() in NON_EDITABLE_EXTENSIONS:
                disable_edit = True
        
        if disable_edit:
            self.chk_edit.value = False
            self.chk_edit.enabled = False
        else:
            self.chk_edit.enabled = True

    def action_select_file(self, widget):
        def on_picked(result_paths):
            self.app.main_window.content = self.content_box
            if result_paths:
                fname = str(result_paths[0])
                self.selected_file_path = fname
                self.lbl_file_path.text = f"Fichier : {fname}"
                self.log_ui(f"Fichier sélectionné : {fname}", "green")
                self._update_edit_option_state()
            else:
                self.log_ui("Sélection annulée.", "yellow")
        
        from drimesyncunofficial.constants import ANDROID_DOWNLOAD_PATH
        browser = AndroidFileBrowser(self.app, on_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=False)                       
        self.app.main_window.content = browser

    def action_select_folder(self, widget):
        def on_picked(result_path):
            self.app.main_window.content = self.content_box
            if result_path:
                fname = str(result_path)
                self.selected_file_path = fname
                self.lbl_file_path.text = f"Dossier : {fname}"
                self.log_ui(f"Dossier sélectionné : {fname}", "green")
                self._update_edit_option_state()
            else:
                self.log_ui("Sélection annulée.", "yellow")
        
        from drimesyncunofficial.constants import ANDROID_DOWNLOAD_PATH
        browser = AndroidFileBrowser(self.app, on_picked, initial_path=ANDROID_DOWNLOAD_PATH, folder_selection_mode=True)
        self.app.main_window.content = browser

    def action_select_file_desktop(self, widget):
        async def _ask():
            try:
                files = await self.app.main_window.dialog(toga.OpenFileDialog("Choisir un fichier", multiple_select=False))
                if files:
                    fname = str(files[0]) if isinstance(files, list) else str(files)
                    self.selected_file_path = fname
                    self.lbl_file_path.text = f"Fichier: {fname}"
                    self.log_ui(f"Fichier sélectionné: {fname}")
                    self._update_edit_option_state()
            except ValueError: pass 
        self.app.loop.create_task(_ask())

    def action_select_folder_desktop(self, widget):
        async def _ask():
            try:
                folder = await self.app.main_window.dialog(toga.SelectFolderDialog("Choisir un dossier"))
                if folder:
                    self.selected_file_path = folder
                    self.lbl_file_path.text = f"Dossier: {folder}"
                    self.log_ui(f"Dossier sélectionné: {folder}")
                    self._update_edit_option_state()
            except ValueError: pass 
        self.app.loop.create_task(_ask())

    async def action_generate(self, widget):
        if not self.selected_file_path:
            await self.app.main_window.dialog(toga.InfoDialog("Attention", "Veuillez choisir un fichier ou un dossier d'abord."))
            return

        link_pwd = None
        expiration = None
        
        if self.chk_link_pwd.value:
            link_pwd = self.input_link_pwd.value
            if not link_pwd:
                await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Vous avez activé le mot de passe du Lien, mais le champ est vide."))
                return

        if self.chk_expiration.value:
            expiration = f"{self.input_date.value}T23:59:59Z"
            
        notify = self.chk_notify.value
        allow_download = self.chk_download.value
        allow_edit = self.chk_edit.value

        if self.switch_secure.value:
            MAX_SIZE_CAPSULE = 150 * 1024 * 1024
            current_size = get_total_size(self.selected_file_path)
            
            if current_size > MAX_SIZE_CAPSULE:
                size_mb = current_size / (1024**2)
                msg = tr("capsule_size_error", "Size exceeds limit").format(size=size_mb)
                await self.app.main_window.dialog(toga.ErrorDialog(tr("capsule_too_large", "Capsule too large"), msg))
                return
            
            pwd = self.input_password.value
            if not pwd:
                await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Le mot de passe de déchiffrement (Capsule) est obligatoire."))
                return

            if not validate_password_compliance(pwd):
                msg = (
                    "Le mot de passe Capsule est trop faible !\n\n"
                    "Règles (ANSSI) :\n"
                    "- Minimum 12 caractères\n"
                    "- Au moins 1 Majuscule\n"
                    "- Au moins 1 Minuscule\n"
                    "- Au moins 1 Chiffre\n"
                    "- Au moins 1 Caractère spécial"
                )
                await self.app.main_window.dialog(toga.ErrorDialog("Sécurité Faible", msg))
                return
            
            if allow_edit:
                allow_edit = False

            self.log_ui("Génération de la capsule en cours... Patientez...", COL_VIOLET2)
            await asyncio.to_thread(self._generate_capsule_logic, pwd, link_pwd=link_pwd, expiration=expiration, notify=notify, allow_download=allow_download)
            
        else:
            self.log_ui("Mode Standard : Préparation de l'upload...", COL_BLEU)
            await asyncio.to_thread(self._generate_cloud_link_logic, link_pwd=link_pwd, expiration=expiration, notify=notify, allow_edit=allow_edit, allow_download=allow_download)

    def _generate_capsule_logic(self, password, link_pwd=None, expiration=None, notify=False, allow_download=True):
        """Logique de génération de la capsule sécurisée (thread)."""
        target_path = self.selected_file_path
        if not target_path or not os.path.exists(target_path):
             self.log_ui("Fichier introuvable.", COL_ROUGE)
             return

        temp_zip_path = None
        temp_html_path = None

        try:
            file_to_process = target_path
            
            if not isinstance(target_path, str): target_path = str(target_path)
            
            if os.path.isdir(target_path):
                 self.log_ui(f"Compression du dossier pour capsule...", COL_VIOLET2)
                 zip_name = f"{os.path.basename(target_path)}.zip"
                 temp_dir = self.app.paths.cache if hasattr(self.app.paths, 'cache') else Path(os.path.dirname(target_path))
                 temp_zip_path = os.path.join(temp_dir, zip_name)
                 
                 if make_zip(target_path, temp_zip_path):
                     file_to_process = temp_zip_path
                 else:
                     self.log_ui("❌ Erreur compression ZIP.", COL_ROUGE)
                     return

            self.log_ui("Chiffrement Zero-Knowledge (Argon2id)...", COL_BLEU2)
            
            import uuid
            mgr = CapsuleManager()
            original_name = os.path.basename(file_to_process)
            html_name = f"Capsule_{uuid.uuid4().hex[:12]}.html"
            
            temp_dir = self.app.paths.cache if hasattr(self.app.paths, 'cache') else Path(os.path.dirname(str(file_to_process)))
            temp_html_path = os.path.join(temp_dir, html_name)

            salt = mgr.create_capsule(file_to_process, temp_html_path, password)
            
            if not salt:
                self.log_ui("❌ Échec de création de la capsule.", COL_ROUGE)
                return

            self.log_ui(f"✅ Capsule créée : {html_name}", COL_VERT)
            
            def _show_token():
                self.input_salt.value = salt
                self.app.main_window.dialog(toga.InfoDialog("Token de Déchiffrement", f"IMPORTANT : Voici le Token (Sel) nécessaire pour déverrouiller le fichier :\n\n{salt}\n\nCopiez-le, il ne sera plus affiché !"))
            self.app.loop.call_soon_threadsafe(_show_token)

            self.log_ui(f"Upload de la capsule sécurisée...")
            
            final_rel_path = f"shared_files/{html_name}"
            f_size = os.path.getsize(temp_html_path)

            def check_status(): return True

            resp_dict = self.app.api_client.upload_file(
                file_path=str(temp_html_path),
                workspace_id="0",
                relative_path=final_rel_path,
                progress_callback=lambda transferred: self.log_ui(f"Upload: {transferred/f_size*100:.1f}%", COL_BLEU2) if f_size > 0 else None,
                check_status_callback=check_status
            )
            
            entry_id = resp_dict.get('id') if resp_dict else None
            
            if not entry_id:
                self.log_ui("❌ Erreur Upload Capsule.", COL_ROUGE)
                return

            self.log_ui(f"Génération du lien public...", COL_JAUNE)
            
            link_resp = self.app.api_client.create_share_link(
                entry_id,
                password=None,
                expires_at=expiration,
                allow_edit=False,
                allow_download=True,
                notify_on_download=notify
            )
            
            final_link = None
            if link_resp.status_code == 200:
                l_data = link_resp.json()
                if l_data.get('status') == 'success':
                     final_link = f"https://dri.me/{l_data.get('link', {}).get('hash')}"

            if final_link:
                self.log_ui(f"✅ LIEN CAPSULE : {final_link}", COL_VIOLET)
                def _show_link():
                    self.input_std_link.value = final_link
                self.app.loop.call_soon_threadsafe(_show_link)
            else:
                self.log_ui("❌ Erreur Lien.", COL_ROUGE)

        except Exception as e:
            self.log_ui(f"Erreur Capsule: {e}", COL_ROUGE)
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path): 
                try: os.remove(temp_zip_path)
                except: pass
            if temp_html_path and os.path.exists(temp_html_path):
                try: os.remove(temp_html_path)
                except: pass

    def _generate_cloud_link_logic(self, link_pwd=None, expiration=None, notify=False, allow_edit=False, allow_download=True):
        target_path = self.selected_file_path
        if not target_path or not os.path.exists(target_path):
             self.log_ui("Fichier introuvable.", COL_ROUGE)
             return

        temp_zip_path = None
        
        try:
            file_to_upload = target_path
            
            if not isinstance(target_path, str): 
                 target_path = str(target_path)
            
            if os.path.isdir(target_path):
                self.log_ui(f"Compression du dossier '{os.path.basename(target_path)}'...", COL_VIOLET2)
                zip_name = f"{os.path.basename(target_path)}.zip"
                temp_dir = self.app.paths.cache if hasattr(self.app.paths, 'cache') else Path(os.path.dirname(target_path))
                temp_zip_path = os.path.join(temp_dir, zip_name)
                
                if make_zip(target_path, temp_zip_path):
                    self.log_ui(f"Dossier compressé : {zip_name}", COL_VERT)
                    file_to_upload = temp_zip_path
                else:
                    self.log_ui("❌ Erreur lors de la compression ZIP.", COL_ROUGE)
                    return

            file_name_final = os.path.basename(file_to_upload)

            shared_folder_name = "shared_files"
            final_rel_path = f"{shared_folder_name}/{file_name_final}"
            
            self.log_ui(f"Upload vers Drime (Workspace 0)...")
            
            def progress_cb(total_transferred):
                 pass
            
            def check_status():
                return True

            try:
                f_size = os.path.getsize(file_to_upload)
                
                resp_dict = self.app.api_client.upload_file(
                    file_path=str(file_to_upload),
                    workspace_id="0",
                    relative_path=final_rel_path,
                    progress_callback=lambda transferred: self.log_ui(f"Upload: {transferred/f_size*100:.1f}%", COL_BLEU2) if f_size > 0 else None,
                    check_status_callback=check_status
                )
                
                
                
            except Exception as e:
                self.log_ui(f"❌ Erreur Upload: {e}", COL_ROUGE)
                if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)
                return

            
            entry_id = None
            if resp_dict:
                 entry_id = resp_dict.get('id')
            
            if not entry_id:
                 self.log_ui(f"❌ Upload réussi mais ID introuvable.", COL_ROUGE)
                 if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)
                 return


            self.log_ui(f"✅ Upload terminé (ID: {entry_id})", COL_VERT)

            self.log_ui(f"Génération du lien de partage (ID={entry_id})...", COL_JAUNE)
            self.log_ui(f"Options: Pwd={'Oui' if link_pwd else 'Non'} Exp={expiration} DL={allow_download} Edit={allow_edit} Notify={notify}", COL_BLEU, debug=True)

            link_resp = self.app.api_client.create_share_link(
                entry_id, 
                password=link_pwd, 
                expires_at=expiration, 
                allow_edit=allow_edit, 
                allow_download=allow_download,
                notify_on_download=notify
            )
            
            self.log_ui(f"Reponse Link: {link_resp.status_code} - {link_resp.text[:200]}", COL_BLEU, debug=True)

            final_link = None
            if link_resp.status_code == 200:
                l_data = link_resp.json()
                if l_data.get('status') == 'success':
                    link_hash = l_data.get('link', {}).get('hash')
                    final_link = f"https://dri.me/{link_hash}"
            
            if final_link:
                self.log_ui(f"✅ LIEN GÉNÉRÉ : {final_link}", COL_VIOLET2)
                def _show_link():
                    self.input_std_link.value = final_link 
                
                self.app.loop.call_soon_threadsafe(_show_link)
            else:
                 self.log_ui(f"❌ Erreur Link: {link_resp.text}", COL_ROUGE)

            if temp_zip_path and os.path.exists(temp_zip_path):
                try: os.remove(temp_zip_path)
                except: pass

        except Exception as e:
            self.log_ui(f"Erreur Standard Share: {e}", COL_ROUGE)
            if temp_zip_path and os.path.exists(temp_zip_path):
                try: os.remove(temp_zip_path)
                except: pass











