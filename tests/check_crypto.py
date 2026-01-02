try:
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    print("Argon2id: AVAILABLE")
except ImportError:
    print("Argon2id: MISSING")

try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    print("ChaCha20Poly1305: AVAILABLE")
except ImportError:
    print("ChaCha20Poly1305: MISSING")
