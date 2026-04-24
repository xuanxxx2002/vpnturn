import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# --- 金鑰衍生 ---
def derive_key(shared_secret: bytes, salt: bytes | None = None) -> bytes:
    """使用 HKDF-SHA256 從共享密碼衍生 256-bit 金鑰"""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,                          # 256 bit
        salt=salt or b"vpntun-salt-v1",
        info=b"vpntun-aes256gcm",
    )
    return hkdf.derive(shared_secret)

# --- 加密封包 ---
def encrypt_packet(key: bytes, plaintext: bytes) -> bytes:
    """
    格式: [12B nonce][ciphertext + 16B GCM tag]
    GCM 提供加密 + 完整性驗證（AEAD），無需額外 HMAC
    """
    nonce = os.urandom(12)                  # GCM 標準 96-bit nonce
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ciphertext

# --- 解密封包 ---
def decrypt_packet(key: bytes, data: bytes) -> bytes:
    """解密並驗證完整性；GCM tag 驗證失敗時拋出 InvalidTag"""
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
