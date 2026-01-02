import toga
import json
import asyncio
import os
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD, CENTER
from drimesyncunofficial.constants import COL_VERT, COL_GRIS, COL_TEXT_GRIS, COL_JAUNE, COL_ROUGE, COL_VIOLET, COL_BLEU, MODE_NO_ENC, MODE_E2EE_STANDARD, MODE_E2EE_ADVANCED, MODE_E2EE_ZK, E2EE_CRYPTO_ALGO
from drimesyncunofficial.utils import set_secure_secret, get_secure_secret, generate_2fa_secret, verify_2fa_code, get_salt_as_base64, save_salt_from_base64, get_salt_path
from drimesyncunofficial.utils import generate_qr_image_bytes
from drimesyncunofficial.android_utils import request_ignore_battery_optimizations_intent, is_ignoring_battery_optimizations, copy_to_clipboard_android
from drimesyncunofficial.i18n import tr

class SecurityManager:
    """
    Gestionnaire de Sécurité.
    Responsable de l'interface de configuration du Chiffrement (E2EE) et de la Double Authentification (2FA).
    Gère également la sauvegarde sécurisée des secrets (via Keyring sur Desktop).
    """
    def __init__(self, app):
        self.app = app
        self.window = None
        self.current_mode = self.app.config_data.get('encryption_mode', MODE_NO_ENC)
        self.current_password = self.app.config_data.get('e2ee_password', '')
        self.secret_2fa = self.app.config_data.get('2fa_secret', '')
        self.is_2fa_active = bool(self.secret_2fa)
        self.mode_switches = {}
        self.input_password = None
        self.lbl_password_status = None
        self.btn_save = None
        self.switch_2fa = None
        self.input_secret_2fa = None
        self.input_verify_code = None
        self.box_2fa_setup = None
        self.lbl_2fa_status = None
        self.qr_image_view = None

    def show(self):
        """Construit et affiche la fenêtre de configuration de sécurité."""
        container = toga.ScrollContainer(horizontal=False)
        self.main_box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        
        self.container_2fa_wrapper = toga.Box(style=Pack(direction=COLUMN))
        
        self.main_box.add(toga.Label(tr("sec_title_enc", "1. Chiffrement des Données (E2EE)"), style=Pack(font_weight=BOLD, color=COL_ROUGE, margin_bottom=5, font_size=12)))
        self.main_box.add(toga.Label(f"{tr('sec_algo_label', 'Algorithme')} : {E2EE_CRYPTO_ALGO}", style=Pack(margin_bottom=15, font_size=8, color='gray')))
        
        modes = [
            (MODE_NO_ENC, tr("sec_mode_none", "Pas de chiffrement"), COL_BLEU),
            (MODE_E2EE_STANDARD, tr("sec_mode_std", "Chiffrement Standard"), COL_VERT),
            (MODE_E2EE_ADVANCED, tr("sec_mode_adv", "Chiffrement Avancé"), COL_JAUNE),
            (MODE_E2EE_ZK, tr("sec_mode_zk", "Zero Knowledge"), COL_ROUGE)
        ]
        
        for value, label, color in modes:
            initial_value = (value == self.current_mode)
            switch = toga.Switch(label, value=initial_value, id=value, style=Pack(color=color, font_weight=BOLD, margin_bottom=5), on_change=self.on_mode_change)
            self.mode_switches[value] = switch
            self.main_box.add(switch)
            
        self.main_box.add(toga.Label(tr("sec_pwd_label", "Mot de Passe E2EE :"), style=Pack(margin_top=15, margin_bottom=5, font_weight=BOLD)))
        self.input_password = toga.PasswordInput(
            value=self.current_password, 
            placeholder=tr("sec_pwd_placeholder", "Votre mot de passe secret"), 
            style=Pack(margin_bottom=5), 
            on_change=self.on_password_change
        )
        self.main_box.add(self.input_password)
        
        self.lbl_password_status = toga.Label(tr("sec_pwd_status", "Statut mot de passe"), style=Pack(font_size=8, margin_bottom=20))
        self.main_box.add(self.lbl_password_status)
        
        self.main_box.add(toga.Divider(style=Pack(margin_bottom=20)))
        
        self.main_box.add(toga.Label(tr("sec_keys_title", "2. Clés de Chiffrement (Avancé)"), style=Pack(font_weight=BOLD, color='orange', margin_bottom=10, font_size=12)))
        self.main_box.add(toga.Label(tr("sec_keys_desc", "Gérez manuellement votre clé de chiffrement (Salt) pour la portabilité entre appareils."), style=Pack(font_size=8, margin_bottom=10)))
        
        row_salt = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        btn_export_salt = toga.Button(tr("btn_export_salt", "Exporter le Sel (Base64)"), on_press=self.action_export_salt, style=Pack(flex=1, margin_right=5))
        btn_import_salt = toga.Button(tr("btn_import_salt", "Importer un Sel"), on_press=self.action_import_salt, style=Pack(flex=1, margin_left=5, background_color=COL_ROUGE, color='white'))
        row_salt.add(btn_export_salt)
        row_salt.add(btn_import_salt)
        self.main_box.add(row_salt)
                                
        btn_renew_salt = toga.Button(tr("btn_renew_salt", "⚠️ Renouveller le Sel (DANGER)"), on_press=self.action_renew_salt, style=Pack(background_color=COL_ROUGE, color='white', font_weight=BOLD, margin_bottom=10))
        self.main_box.add(btn_renew_salt)
        
        self.main_box.add(toga.Divider(style=Pack(margin_bottom=20)))

        self.main_box.add(toga.Label(tr("sec_2fa_title", "3. Protection de l'Application (2FA)"), style=Pack(font_weight=BOLD, color=COL_VIOLET, margin_bottom=10, font_size=12)))
        self.switch_2fa = toga.Switch(tr("sec_2fa_switch", "Activer la Double Authentification"), value=self.is_2fa_active, on_change=self.on_2fa_toggle, style=Pack(margin_bottom=10))
        self.main_box.add(self.switch_2fa)
        
        self.lbl_2fa_status = toga.Label(
            tr("sec_2fa_active", "✅ 2FA ACTIF") if self.is_2fa_active else tr("sec_2fa_inactive", "❌ 2FA INACTIF"),
            style=Pack(margin_bottom=10, font_size=9, color=COL_VERT if self.is_2fa_active else COL_GRIS)
        )
        self.main_box.add(self.lbl_2fa_status)
        
        self.main_box.add(self.container_2fa_wrapper)
        
        self.box_2fa_setup = toga.Box(style=Pack(direction=COLUMN, margin_left=10, margin_bottom=10))
        self.box_2fa_setup.add(toga.Label(tr("sec_2fa_step1", "1. Scannez ce QR Code :"), style=Pack(font_weight=BOLD, font_size=8, margin_bottom=5)))
        
        self.qr_image_view = toga.ImageView(style=Pack(width=150, height=150, margin_bottom=10, align_items=CENTER))
        self.box_2fa_setup.add(self.qr_image_view)
        
        self.box_2fa_setup.add(toga.Label(tr("sec_2fa_or_copy", "OU Copiez la clé secrète :"), style=Pack(font_weight=BOLD, font_size=8)))
        self.input_secret_2fa = toga.TextInput(
            value=self.secret_2fa if self.secret_2fa else generate_2fa_secret(), 
            placeholder="JBSWY...", 
            style=Pack(margin_bottom=15, font_family='monospace', background_color=COL_JAUNE)
        )
        self.box_2fa_setup.add(self.input_secret_2fa)

        import datetime
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.lbl_time_debug = toga.Label(f"Heure App : {now_str}", style=Pack(font_size=8, color='gray', margin_bottom=5))
        self.box_2fa_setup.add(self.lbl_time_debug)
        
        self.box_2fa_setup.add(toga.Label(tr("sec_2fa_step2", "2. Entrez le code (6 chiffres) :"), style=Pack(font_weight=BOLD, font_size=8)))
        
        row_verify = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        self.input_verify_code = toga.TextInput(placeholder="Ex: 123456", style=Pack(flex=1, margin_right=5))
        btn_verify_2fa = toga.Button(tr("btn_verify", "Vérifier"), on_press=self.action_verify_2fa, style=Pack(width=100))
        row_verify.add(self.input_verify_code)
        row_verify.add(btn_verify_2fa)
        self.box_2fa_setup.add(row_verify)
        
        if self.is_2fa_active:
             self.container_2fa_wrapper.add(self.box_2fa_setup)
        
        self.main_box.add(toga.Divider(style=Pack(margin_bottom=20)))
        
                          
        
        row_btns = toga.Box(style=Pack(direction=ROW, margin_top=20))
        btn_cancel = toga.Button(tr("btn_close", "Fermer"), on_press=self.app.retour_arriere, style=Pack(flex=1, margin_right=5))
        self.btn_save = toga.Button(tr("btn_save_all", "ENREGISTRER TOUT"), on_press=self.action_save, style=Pack(flex=1, margin_left=5, background_color=COL_VERT, color='white', font_weight=BOLD))
        row_btns.add(btn_cancel)
        row_btns.add(self.btn_save)
        self.main_box.add(row_btns)
        
        container.content = self.main_box
        self.app.changer_ecran(container)
        self.check_required_fields()

    def on_2fa_toggle(self, widget):
        """Active ou désactive l'interface de configuration 2FA via le Wrapper."""
        self.is_2fa_active = widget.value
        
        if self.is_2fa_active:
            if self.box_2fa_setup not in self.container_2fa_wrapper.children:
                self.container_2fa_wrapper.add(self.box_2fa_setup)
            
            self.lbl_2fa_status.text = tr("sec_2fa_config_req", "⚠️ Configuration requise...")
            self.lbl_2fa_status.style.color = COL_JAUNE
            
            secret = self.input_secret_2fa.value
            if not secret:
                secret = generate_2fa_secret()
                self.input_secret_2fa.value = secret
            
            try:
                img_bytes = generate_qr_image_bytes(secret, account_name="Utilisateur")
                self.qr_image_view.image = toga.Image(src=img_bytes)
            except Exception as e:
                print(f"Erreur QR Code: {e}")
        else:
            if self.box_2fa_setup in self.container_2fa_wrapper.children:
                 self.container_2fa_wrapper.remove(self.box_2fa_setup)

            self.lbl_2fa_status.text = tr("sec_2fa_will_disable", "❌ 2FA sera DÉSACTIVÉ.")
            self.lbl_2fa_status.style.color = COL_ROUGE
            self.input_secret_2fa.value = ""
            self.secret_2fa = "" 


    async def action_verify_2fa(self, widget):
        """Vérifie le code TOTP pour valider l'activation du 2FA."""
        secret = self.input_secret_2fa.value.strip()
        code = self.input_verify_code.value.strip()
        
        if verify_2fa_code(secret, code):
            self.secret_2fa = secret
            self.lbl_2fa_status.text = "✅ Code valide ! Enregistrez pour activer."
            self.lbl_2fa_status.style.color = COL_VERT
            self.box_2fa_setup.style.visibility = 'hidden'
            self.box_2fa_setup.style.height = 0
            await self.app.main_window.dialog(toga.InfoDialog("Succès", "Code valide. Le 2FA est prêt."))
        else:
            await self.app.main_window.dialog(toga.ErrorDialog(
                "Code Incorrect", 
                "Le code est invalide.\n\n"
                "1. Avez-vous scanné le NOUVEAU QR Code affiché ?\n"
                "   (Supprimez l'ancien compte dans votre appli Authenticator si besoin)\n\n"
                "2. Vérifiez que l'heure de votre PC est parfaitement synchronisée."
            ))

    async def action_export_salt(self, widget):
        """Affiche l'écran d'export du Sel (Plein écran pour Android)."""
        salt_b64 = get_salt_as_base64(self.app.paths)
        if not salt_b64:
            await self.app.main_window.dialog(toga.ErrorDialog(tr("error", "Erreur"), tr("sec_err_salt_missing", "Impossible de lire le Salt (Fichier manquant ?)")))
            return
        
        box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        box.add(toga.Label(tr("sec_export_title", "EXPORT DU SEL DE CHIFFREMENT"), style=Pack(font_weight=BOLD, color=COL_BLEU, margin_bottom=20, font_size=12)))
        box.add(toga.Label(tr("sec_export_desc", "Copiez cette chaîne secrète et importez-la sur votre autre appareil :"), style=Pack(margin_bottom=10)))
        
        input_salt = toga.TextInput(value=salt_b64, readonly=True, style=Pack(margin_bottom=10, background_color=COL_JAUNE, font_family='monospace'))
        box.add(input_salt)
        
        def copy_clipboard(w):
            success = False
            try:
                if hasattr(self.app, 'clipboard'):
                    self.app.clipboard.set_text(salt_b64)
                    success = True
                elif hasattr(self.app.main_window, 'clipboard'): 
                    self.app.main_window.clipboard.set_text(salt_b64)
                    success = True
            except: pass

            if not success and toga.platform.current_platform == 'android':
                if copy_to_clipboard_android(salt_b64): success = True

            if success:
                self.app.main_window.info_dialog(tr("copied", "Copié"), tr("sec_salt_copied", "Salt copié dans le presse-papier !"))
            else:
                self.app.main_window.info_dialog(tr("info", "Info"), tr("sec_clipboard_err", "Presse-papier non supporté. Veuillez copier manuellement."))

        btn_copy = toga.Button(tr("btn_copy", "COPIER"), on_press=copy_clipboard, style=Pack(margin_bottom=20, background_color=COL_BLEU, color='white'))
        box.add(btn_copy)
        
        box.add(toga.Label(tr("sec_salt_warning", "ATTENTION : Ne partagez jamais ce code !"), style=Pack(color=COL_ROUGE, font_size=8, margin_bottom=20)))
        
        btn_back = toga.Button(tr("btn_back_security", "⬅ Retour Sécurité"), on_press=self.show_security_menu_again, style=Pack(margin_top=10))
        box.add(btn_back)
        
        self.app.changer_ecran(box)
    
    async def action_renew_salt(self, widget):
        """Logic to renew the salt with warnings."""
        confirm = await self.app.main_window.dialog(toga.QuestionDialog(
            tr("sec_renew_title", "DANGER EXTRÊME - CONFIRMATION"),
            tr("sec_renew_msg", "ATTENTION : Générer un nouveau Sel rendra ILLISIBLES tous vos fichiers déjà chiffrés sur le Cloud.\n\nCette action est irréversible. Vous devrez re-uploader tous vos fichiers chiffrés.\n\nÊtes-vous CERTAIN de vouloir continuer ?")
        ))
        if not confirm: return
        
        try:
            salt_path = get_salt_path(self.app.paths)
            new_salt = os.urandom(16)
            salt_path.write_bytes(new_salt)
            await self.app.main_window.dialog(toga.InfoDialog("Succès", "Nouveau Sel généré avec succès."))
        except Exception as e:
            await self.app.main_window.dialog(toga.ErrorDialog("Erreur", f"Échec lors du renouvellement du sel : {e}"))

    async def action_import_salt(self, widget):
        """Affiche l'écran d'import du Sel (Plein écran pour Android)."""
        confirm = await self.app.main_window.dialog(toga.QuestionDialog(
            tr("sec_import_title", "DANGER CRITIQUE"),
            tr("sec_import_msg", "Importer un nouveau Salt rendra ILLISIBLES tous vos fichiers déjà chiffrés sur cet appareil.\n\nÊtes-vous sûr de vouloir écraser le Salt actuel ?")
        ))
        if not confirm: return
        
        box = toga.Box(style=Pack(direction=COLUMN, margin=20))
        box.add(toga.Label(tr("sec_import_header", "IMPORTATION DU SEL"), style=Pack(font_weight=BOLD, color=COL_ROUGE, margin_bottom=20, font_size=12)))
        box.add(toga.Label(tr("sec_import_desc", "Collez ici la chaîne Salt (Base64) de votre autre appareil :"), style=Pack(margin_bottom=10)))
        
        self.input_import_salt = toga.TextInput(placeholder="Ex: ...=", style=Pack(margin_bottom=20, font_family='monospace'))
        box.add(self.input_import_salt)
        
        async def do_import(w):
            val = self.input_import_salt.value.strip()
            if not val: return
            if save_salt_from_base64(self.app.paths, val):
                await self.app.main_window.dialog(toga.InfoDialog("Succès", "Nouveau Salt importé avec succès."))
                self.app.retour_arriere(w)                          
            else:
                await self.app.main_window.dialog(toga.ErrorDialog("Erreur", "Format Base64 invalide."))

        btn_import = toga.Button(tr("btn_import_overwrite", "IMPORTER ET ÉCRASER"), on_press=do_import, style=Pack(background_color=COL_ROUGE, color='white', font_weight=BOLD, margin_bottom=10))
        box.add(btn_import)
        
        btn_back = toga.Button(tr("btn_cancel_return", "Annuler / Retour"), on_press=self.show_security_menu_again, style=Pack(margin_top=10))
        box.add(btn_back)
        
        self.app.changer_ecran(box)

    def show_security_menu_again(self, widget):
        """Helper pour revenir au menu principal de sécurité."""
        self.app.retour_arriere(widget)

    def on_mode_change(self, widget):
        """Gère l'exclusivité des switchs de mode de chiffrement."""
        if widget.value:
            new_mode_id = widget.id
            for mode_id, switch in self.mode_switches.items():
                if mode_id != new_mode_id:
                    switch.value = False
            self.current_mode = new_mode_id
        elif widget.id == self.current_mode:
            widget.value = True 
        self.check_required_fields()

    def on_password_change(self, widget):
        self.current_password = widget.value.strip()
        self.check_required_fields()

    def check_required_fields(self):
        """Vérifie que le mot de passe est présent si un mode chiffré est sélectionné."""
        is_e2ee = self.current_mode != MODE_NO_ENC
        pwd_check = bool(self.current_password)
        if is_e2ee and not pwd_check:
            self.lbl_password_status.text = tr("sec_pwd_req", "⚠️ Mot de passe requis.")
            self.lbl_password_status.style.color = COL_ROUGE
            self.btn_save.enabled = False
        else:
            self.lbl_password_status.text = "OK"
            self.lbl_password_status.style.color = COL_VERT
            self.btn_save.enabled = True

    async def action_save(self, widget):
        """Sauvegarde la configuration et les secrets."""
        if self.switch_2fa.value and not self.secret_2fa:
             await self.app.main_window.dialog(toga.ErrorDialog("Erreur 2FA", "Veuillez vérifier le code 2FA avant d'enregistrer."))
             return
             
        old_mode = self.app.config_data.get('encryption_mode', MODE_NO_ENC)
        old_pass = self.app.config_data.get('e2ee_password', '')
        
        must_force_sync = False
        if self.current_mode != old_mode:
             if self.current_mode != MODE_NO_ENC or old_mode != MODE_NO_ENC: must_force_sync = True
             
        if self.current_mode != MODE_NO_ENC and self.current_password != old_pass: must_force_sync = True
        
        if must_force_sync:
             if not await self.app.main_window.dialog(toga.QuestionDialog("CHANGEMENT CRITIQUE", "Changement de chiffrement détecté. Synchro forcée requise. Confirmer ?")):
                 return
                 
        self.app.config_data['encryption_mode'] = self.current_mode
        self.app.config_data['e2ee_password'] = self.current_password
        self.app.config_data['2fa_secret'] = self.secret_2fa
        
                                               
        saved_pass_keyring = set_secure_secret("e2ee_password", self.current_password)
        saved_2fa_keyring = False
        if self.secret_2fa:
            saved_2fa_keyring = set_secure_secret("2fa_secret", self.secret_2fa)
        else:
            set_secure_secret("2fa_secret", "") 
            
                                     
        config_to_save = self.app.config_data.copy()
        
                                                  
        if saved_pass_keyring: config_to_save['e2ee_password'] = ""
        else: config_to_save['e2ee_password'] = self.current_password
        
        if saved_2fa_keyring: config_to_save['2fa_secret'] = ""
        elif self.secret_2fa: config_to_save['2fa_secret'] = self.secret_2fa
        else: config_to_save['2fa_secret'] = ""
        
                                                
        is_desktop = toga.platform.current_platform not in {'android', 'iOS', 'web'}
        if is_desktop:
            config_to_save['api_key'] = ""
            config_to_save['e2ee_password'] = ""
            config_to_save['2fa_secret'] = ""
            
        try:
            with open(self.app.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4)
            
            self.app.retour_arriere(widget)
            
            if must_force_sync:
                 await self.app.main_window.dialog(toga.ErrorDialog("Info", "Paramètres sauvegardés. Pensez à la Synchro Forcée."))
            else:
                 await self.app.main_window.dialog(toga.InfoDialog("Succès", "Paramètres de sécurité sauvegardés."))
                 
        except Exception as e:
            await self.app.main_window.dialog(toga.ErrorDialog("Erreur", f"{e}"))