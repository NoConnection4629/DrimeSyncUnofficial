import os
import json
import base64
import secrets
import string
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class CapsuleManager:
    """
    Génère une 'Capsule' HTML autonome Zero-Knowledge.
    Niveau de sécurité : PARANOÏAQUE (2M itérations).
    """
    
    N_ITERATIONS = 2000000

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coffre-Fort Numérique</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:
        .container { background:
        h2 { margin-top: 0; color:
        .icon { font-size: 3rem; margin-bottom: 10px; display: block; }
        p { font-size: 0.95rem; color:
        .input-group { margin-bottom: 20px; text-align: left; }
        label { display: block; font-size: 0.75rem; font-weight: bold; margin-bottom: 8px; color:
        .input-wrapper { position: relative; }
        input { width: 100%; padding: 14px; background:
        input:focus { border-color:
        .toggle-pwd { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); cursor: pointer; opacity: 0.6; font-size: 1.2rem; background: none; border: none; color: white; }
        .toggle-pwd:hover { opacity: 1; }
        button.main-btn { background:
        button.main-btn:hover { background:
        button.main-btn:disabled { background:
        .error { background:
        .success { background:
        .info { color:
        .meta-info { font-size: 0.8rem; color:
        .tech-hint { display: block; margin-top: 5px; font-size: 0.85em; opacity: 0.8; font-weight: normal; }
    </style>
</head>
<body>
    <div class="container">
        <span class="icon">🔒</span>
        <h2>COFFRE FORT NUMÉRIQUE</h2>
        <p>Ce fichier est chiffré (Zero-Knowledge).<br>Le contenu et le nom sont masqués.</p>
        <div class="input-group">
            <label>1. Mot de Passe</label>
            <div class="input-wrapper">
                <input type="password" id="pwd" placeholder="Collez le mot de passe...">
                <button class="toggle-pwd" onclick="togglePwd()">👁️</button>
            </div>
        </div>
        <div class="input-group">
            <label>2. Token (Sel)</label>
            <input type="text" id="salt" placeholder="XXXX-XXXX-XXXX-XXXX" autocomplete="off">
        </div>
        <button onclick="decrypt()" class="main-btn" id="btn">Déchiffrer le contenu</button>
        <div id="status"></div>
        <div class="meta-info">Secured by DrimeSync Unofficial • AES-256-GCM<br>Iter: __ITER_DISPLAY__</div>
    </div>
    <script>
        const PAYLOAD = "__PAYLOAD__"; 
        const IV_HEX = "__IV__";
        const ITERATIONS = __ITERATIONS__; 
        
        function setStatus(msg, type) {
            const el = document.getElementById('status');
            el.innerHTML = msg; el.className = type; el.style.display = "block";
        }
        function togglePwd() {
            const inp = document.getElementById('pwd');
            inp.type = inp.type === 'password' ? 'text' : 'password';
        }
        function hexToBuf(hex) { return new Uint8Array(hex.match(/.{1,2}/g).map(byte => parseInt(byte, 16))); }

        async function decrypt() {
            const pwd = document.getElementById('pwd').value;
            const saltStr = document.getElementById('salt').value.trim();
            if (!pwd || !saltStr) { setStatus("⚠️ Remplissez les deux champs.", "error"); return; }

            const btn = document.getElementById('btn');
            btn.disabled = true; btn.innerText = "Calcul Cryptographique...";
            
            const iterStr = (ITERATIONS / 1000000).toFixed(1) + "M";
            setStatus(`Dérivation clé maître (${iterStr} itérations)...<br>Cela peut prendre quelques secondes.`, "info");
            
            await new Promise(r => setTimeout(r, 50));

            try {
                const salt = new TextEncoder().encode(saltStr);
                const iv = hexToBuf(IV_HEX);
                const encData = Uint8Array.from(atob(PAYLOAD), c => c.charCodeAt(0));
                
                const pwdKey = await window.crypto.subtle.importKey("raw", new TextEncoder().encode(pwd), "PBKDF2", false, ["deriveKey"]);
                const aesKey = await window.crypto.subtle.deriveKey({ name: "PBKDF2", salt: salt, iterations: ITERATIONS, hash: "SHA-256" }, pwdKey, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
                
                setStatus("Déchiffrement du paquet...", "info");
                const decryptedBuffer = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, aesKey, encData);
                
                const decoder = new TextDecoder();
                const jsonStr = decoder.decode(decryptedBuffer);
                const package = JSON.parse(jsonStr);

                const byteCharacters = atob(package.d);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: package.t });

                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = package.n;
                document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
                
                setStatus(`✅ SUCCÈS !<br>Fichier : <b>${package.n}</b>`, "success");
                btn.innerText = "Fichier Déverrouillé"; btn.disabled = false;
            } catch (e) {
                console.error(e); btn.disabled = false; btn.innerText = "Déchiffrer le contenu";
                
                // --- ICI LE MESSAGE D'ERREUR COMPLET QUE TU AS DEMANDÉ ---
                setStatus(
                    "❌ ÉCHEC.<br>" +
                    "Mot de passe ou Token incorrect.<br>" +
                    "<span class='tech-hint'>Si vous êtes certain de ces informations, votre matériel n'est peut-être pas assez puissant (Manque de RAM).</span>", 
                    "error"
                );
            }
        }
    </script>
</body>
</html>"""

    def generate_human_salt(self, length=16):
        chars = string.ascii_uppercase + string.digits
        raw = ''.join(secrets.choice(chars) for _ in range(length))
        return "-".join(raw[i:i+4] for i in range(0, len(raw), 4))

    def compress_folder(self, folder_path, output_zip_path):
        try:
            folder_path = Path(folder_path)
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=folder_path.parent)
                        zipf.write(file_path, arcname)
            return True
        except Exception as e:
            print(f"Erreur ZIP: {e}")
            return False

    def create_capsule(self, input_path, output_path, password):
        try:
            file_path = Path(input_path)
            secret_salt_str = self.generate_human_salt()
            salt_bytes = secret_salt_str.encode('utf-8')
            
            ext = file_path.suffix.lower()
            mime = "application/octet-stream"
            if ext == '.pdf': mime = "application/pdf"
            elif ext in ['.jpg', '.jpeg']: mime = "image/jpeg"
            elif ext == '.png': mime = "image/png"
            elif ext == '.txt': mime = "text/plain"
            elif ext == '.zip': mime = "application/zip"

            with open(input_path, 'rb') as f:
                file_bytes = f.read()
            
            file_b64 = base64.b64encode(file_bytes).decode('ascii')
            
            secret_package = {
                "n": file_path.name,
                "t": mime,
                "d": file_b64
            }
            
            plaintext_json = json.dumps(secret_package).encode('utf-8')

            iv = os.urandom(12)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=self.N_ITERATIONS, 
            )
            key = kdf.derive(password.encode('utf-8'))

            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(iv, plaintext_json, None)

            payload_final = base64.b64encode(ciphertext).decode('utf-8')
            iv_hex = iv.hex()

            html = self.HTML_TEMPLATE.replace("__PAYLOAD__", payload_final)
            html = html.replace("__IV__", iv_hex)
            
            html = html.replace("__ITERATIONS__", str(self.N_ITERATIONS))
            
            iter_display = f"{self.N_ITERATIONS / 1000000:.1f}M"
            html = html.replace("__ITER_DISPLAY__", iter_display)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
                
            return secret_salt_str

        except Exception as e:
            print(f"Erreur Capsule ZK: {e}")
            return None