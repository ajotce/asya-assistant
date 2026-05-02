from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet


def generate_private_salt() -> str:
    return secrets.token_hex(16)


def derive_private_chat_fernet_key(password_hash: str, salt: str) -> bytes:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_hash.encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(digest)


def encrypt_private_message(*, password_hash: str, salt: str, content: str) -> bytes:
    key = derive_private_chat_fernet_key(password_hash=password_hash, salt=salt)
    return Fernet(key).encrypt(content.encode("utf-8"))


def decrypt_private_message(*, password_hash: str, salt: str, content_encrypted: bytes) -> str:
    key = derive_private_chat_fernet_key(password_hash=password_hash, salt=salt)
    return Fernet(key).decrypt(content_encrypted).decode("utf-8")
