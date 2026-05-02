from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class EncryptionKeyNotConfiguredError(RuntimeError):
    pass


class EncryptionServiceConfigurationError(RuntimeError):
    pass


class SecretDecryptionError(RuntimeError):
    pass


class SecretCryptoService:
    def __init__(self, master_encryption_key: str) -> None:
        self._master_encryption_key = master_encryption_key.strip()

    def encrypt(self, plaintext: str) -> bytes:
        fernet = self._build_fernet()
        return fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, encrypted_value: bytes) -> str:
        fernet = self._build_fernet()
        try:
            raw = fernet.decrypt(encrypted_value)
        except InvalidToken as exc:
            raise SecretDecryptionError("Не удалось расшифровать секрет. Проверьте корректность master key.") from exc
        return raw.decode("utf-8")

    def _build_fernet(self) -> Fernet:
        if not self._master_encryption_key:
            raise EncryptionKeyNotConfiguredError(
                "MASTER_ENCRYPTION_KEY не задан. Шифрование секретов недоступно."
            )

        try:
            return Fernet(self._master_encryption_key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise EncryptionServiceConfigurationError(
                "MASTER_ENCRYPTION_KEY имеет неверный формат. Нужен urlsafe base64-ключ Fernet."
            ) from exc
