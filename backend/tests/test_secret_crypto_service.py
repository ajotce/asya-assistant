from cryptography.fernet import Fernet

from app.services.secret_crypto_service import (
    EncryptionKeyNotConfiguredError,
    SecretCryptoService,
    SecretDecryptionError,
)


def test_encrypt_decrypt_roundtrip() -> None:
    key = Fernet.generate_key().decode("utf-8")
    service = SecretCryptoService(key)

    encrypted = service.encrypt("super-secret-value")
    decrypted = service.decrypt(encrypted)

    assert decrypted == "super-secret-value"


def test_encrypt_uses_nonce_for_different_ciphertext() -> None:
    key = Fernet.generate_key().decode("utf-8")
    service = SecretCryptoService(key)

    first = service.encrypt("same-value")
    second = service.encrypt("same-value")

    assert first != second


def test_decrypt_fails_with_wrong_key() -> None:
    key_one = Fernet.generate_key().decode("utf-8")
    key_two = Fernet.generate_key().decode("utf-8")
    encrypted = SecretCryptoService(key_one).encrypt("secret")
    service_with_wrong_key = SecretCryptoService(key_two)

    try:
        service_with_wrong_key.decrypt(encrypted)
        assert False, "Expected SecretDecryptionError"
    except SecretDecryptionError:
        pass


def test_encrypt_fails_when_master_key_missing() -> None:
    service = SecretCryptoService("")

    try:
        service.encrypt("secret")
        assert False, "Expected EncryptionKeyNotConfiguredError"
    except EncryptionKeyNotConfiguredError:
        pass


def test_decrypt_fails_when_master_key_missing() -> None:
    service = SecretCryptoService("")

    try:
        service.decrypt(b"any")
        assert False, "Expected EncryptionKeyNotConfiguredError"
    except EncryptionKeyNotConfiguredError:
        pass
