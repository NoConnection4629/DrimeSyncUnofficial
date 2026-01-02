import keyring
import sys

SERVICE_NAME = "DrimeSyncUnofficial"
USER_NAME = "api_key"

print(f"--- Diagnostic Keyring ---")
print(f"Backend: {keyring.get_keyring()}")

# Check Exact Match
try:
    pwd = keyring.get_password(SERVICE_NAME, USER_NAME)
    if pwd:
        print(f"[OK] Key found for service='{SERVICE_NAME}', user='{USER_NAME}': {pwd[:5]}...")
    else:
        print(f"[FAIL] No key found for service='{SERVICE_NAME}', user='{USER_NAME}'")
except Exception as e:
    print(f"[ERROR] {e}")

# Check Lowercase Service
try:
    pwd_lower = keyring.get_password(SERVICE_NAME.lower(), USER_NAME)
    if pwd_lower:
        print(f"[INFO] Key found for LOWERCASE service='{SERVICE_NAME.lower()}': {pwd_lower[:5]}...")
except: pass

# Check WinVault Generic (if possible to list) -> Not standard in keyring API
