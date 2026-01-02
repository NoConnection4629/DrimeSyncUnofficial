API_BASE_URL = "https://app.drime.cloud/api/v1"
HTTP_TIMEOUT = 30
COL_VERT = '#2ed573'
COL_BLEU = '#70a1ff'
COL_BLEU2 = '#00C2CB'
COL_JAUNE = '#feca57'
COL_ORANGE = '#e67e22'
COL_ROUGE = '#ff6b81'
COL_VIOLET2 = '#a29bfe'
COL_VIOLET = '#6c5ce7'
COL_GRIS = '#dfe4ea'
COL_TEXT_GRIS = 'black'
COL_BACKGROUND = None
E2EE_SALT_PATH = "E2EE_sync_salt.json"
E2EE_CRYPTO_ALGO = "Argon2id + XChaCha20Poly1305 (IETF)"
SYNC_STATE_FOLDER_NAME = ".SyncStateFiles"
CLOUD_TREE_FILE_NAME = "00_drime_cloud_tree.json"
EXCLUDE_FILE_NAME = "_drimeexclude"
PARTIAL_HASH_CHUNK_SIZE = 4096
MODE_NO_ENC = "NO_ENC"
MODE_E2EE_STANDARD = "E2EE_STANDARD"
MODE_E2EE_ADVANCED = "E2EE_ADVANCED"
MODE_E2EE_ZK = "E2EE_ZK"
CONF_KEY_API_KEY = "api_key"
CONF_KEY_WORKERS = "workers"
CONF_KEY_SEMAPHORES = "semaphores"
CONF_KEY_DEBUG_MODE = "debug_mode"
CONF_KEY_USE_EXCLUSIONS = "use_exclusions"
CONF_KEY_ENCRYPTION_MODE = "encryption_mode"
CONF_KEY_E2EE_PASSWORD = "e2ee_password"
CONF_KEY_2FA_SECRET = "2fa_secret"
CONF_KEY_LAST_EMAIL = "last_email"
CONF_KEY_LANGUAGE = "language"
import toga
try:
    if toga.platform.current_platform == 'android':
        CHUNK_SIZE = 13 * 1024 * 1024
    else:
        CHUNK_SIZE = 25 * 1024 * 1024
except:
    CHUNK_SIZE = 25 * 1024 * 1024

BATCH_SIZE = 10
PART_UPLOAD_RETRIES = 3
ANDROID_DOWNLOAD_PATH = "/storage/emulated/0/Download"