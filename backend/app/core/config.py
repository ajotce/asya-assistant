from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    asya_host: str = Field(default="127.0.0.1", alias="ASYA_HOST")
    asya_port: int = Field(default=8000, alias="ASYA_PORT")
    app_version: str = "0.1.0"

    vsellm_api_key: str = Field(default="", alias="VSELLM_API_KEY")
    vsellm_base_url: str = Field(default="https://api.vsellm.ru/v1", alias="VSELLM_BASE_URL")
    vsellm_vision_model: str = Field(default="", alias="VSELLM_VISION_MODEL")
    vsellm_vision_timeout_seconds: int = Field(default=45, alias="VSELLM_VISION_TIMEOUT_SECONDS")
    default_chat_model: str = Field(default="openai/gpt-5", alias="DEFAULT_CHAT_MODEL")
    default_embedding_model: str = Field(default="", alias="DEFAULT_EMBEDDING_MODEL")
    default_assistant_name: str = Field(default="Asya", alias="DEFAULT_ASSISTANT_NAME")
    default_system_prompt: str = Field(
        default=(
            "Ты — Asya, персональный ИИ-ассистент пользователя. "
            "Общайся на русском языке, но можешь использовать английский при необходимости. "
            "Стиль: деловой, дружелюбный, понятный. "
            "Работай только в рамках текущей сессии и загруженных в ней файлов."
        ),
        alias="DEFAULT_SYSTEM_PROMPT",
    )
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_host: str = Field(default="", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="", alias="POSTGRES_DB")
    postgres_user: str = Field(default="", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_sslmode: str = Field(default="prefer", alias="POSTGRES_SSLMODE")
    sqlite_path: str = Field(default="./data/asya.sqlite3", alias="SQLITE_PATH")
    asya_db_path: str = Field(default="./data/asya-0.2.sqlite3", alias="ASYA_DB_PATH")
    tmp_dir: str = Field(default="./tmp", alias="TMP_DIR")
    file_storage_backend: str = Field(default="local", alias="FILE_STORAGE_BACKEND")
    file_storage_local_dir: str = Field(default="./data/blob", alias="FILE_STORAGE_LOCAL_DIR")
    max_files_per_message: int = Field(default=10, alias="MAX_FILES_PER_MESSAGE")
    max_file_size_mb: int = Field(default=256, alias="MAX_FILE_SIZE_MB")
    documents_converter_enabled: bool = Field(default=False, alias="DOCUMENTS_CONVERTER_ENABLED")
    documents_converter_url: str = Field(default="http://libreoffice:3000", alias="DOCUMENTS_CONVERTER_URL")
    documents_converter_timeout_seconds: int = Field(default=60, alias="DOCUMENTS_CONVERTER_TIMEOUT_SECONDS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    serve_frontend: bool = Field(default=True, alias="SERVE_FRONTEND")
    frontend_dist_path: str = Field(default="../frontend/dist", alias="FRONTEND_DIST_PATH")
    auth_registration_mode: str = Field(default="open", alias="AUTH_REGISTRATION_MODE")
    auth_cookie_name: str = Field(default="asya_session", alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_session_ttl_hours: int = Field(default=168, alias="AUTH_SESSION_TTL_HOURS")
    auth_session_hash_secret: str = Field(default="dev-change-me", alias="AUTH_SESSION_HASH_SECRET")
    signup_token_ttl_hours: int = Field(default=48, alias="SIGNUP_TOKEN_TTL_HOURS")
    public_base_url: str = Field(default="http://localhost:8000", alias="PUBLIC_BASE_URL")
    master_encryption_key: str = Field(default="", alias="MASTER_ENCRYPTION_KEY")
    memory_extraction_enabled: bool = Field(default=True, alias="MEMORY_EXTRACTION_ENABLED")
    oauth_state_ttl_seconds: int = Field(default=900, alias="OAUTH_STATE_TTL_SECONDS")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: str = Field(default="", alias="TELEGRAM_BOT_USERNAME")
    telegram_link_token_ttl_seconds: int = Field(default=900, alias="TELEGRAM_LINK_TOKEN_TTL_SECONDS")
    telegram_link_webhook_secret: str = Field(default="", alias="TELEGRAM_LINK_WEBHOOK_SECRET")

    yandex_speechkit_api_key: str = Field(default="", alias="YANDEX_SPEECHKIT_API_KEY")
    yandex_speechkit_folder_id: str = Field(default="", alias="YANDEX_SPEECHKIT_FOLDER_ID")
    yandex_speechkit_stt_url: str = Field(
        default="https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
        alias="YANDEX_SPEECHKIT_STT_URL",
    )
    yandex_speechkit_tts_url: str = Field(
        default="https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
        alias="YANDEX_SPEECHKIT_TTS_URL",
    )

    gigachat_api_key: str = Field(default="", alias="GIGACHAT_API_KEY")
    gigachat_stt_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1/audio/transcriptions",
        alias="GIGACHAT_STT_URL",
    )
    gigachat_tts_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1/audio/speech",
        alias="GIGACHAT_TTS_URL",
    )

    voice_max_audio_bytes: int = Field(default=15728640, alias="VOICE_MAX_AUDIO_BYTES")
    voice_tts_enabled_default: bool = Field(default=False, alias="VOICE_TTS_ENABLED_DEFAULT")
    diary_audio_dir: str = Field(default="./data/diary_audio", alias="DIARY_AUDIO_DIR")
    export_dir: str = Field(default="./exports", alias="EXPORT_DIR")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_instance_role: str = Field(default="leader", alias="SCHEDULER_INSTANCE_ROLE")
    observer_interval_minutes: int = Field(default=15, alias="OBSERVER_INTERVAL_MINUTES")
    observer_snapshot_retention_days: int = Field(default=30, alias="OBSERVER_SNAPSHOT_RETENTION_DAYS")

    linear_oauth_client_id: str = Field(default="", alias="LINEAR_OAUTH_CLIENT_ID")
    linear_oauth_client_secret: str = Field(default="", alias="LINEAR_OAUTH_CLIENT_SECRET")
    linear_oauth_authorize_url: str = Field(
        default="https://linear.app/oauth/authorize",
        alias="LINEAR_OAUTH_AUTHORIZE_URL",
    )
    linear_oauth_token_url: str = Field(
        default="https://api.linear.app/oauth/token",
        alias="LINEAR_OAUTH_TOKEN_URL",
    )
    linear_oauth_revoke_url: str = Field(
        default="https://api.linear.app/oauth/revoke",
        alias="LINEAR_OAUTH_REVOKE_URL",
    )

    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_authorize_url: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth",
        alias="GOOGLE_OAUTH_AUTHORIZE_URL",
    )
    google_oauth_token_url: str = Field(
        default="https://oauth2.googleapis.com/token",
        alias="GOOGLE_OAUTH_TOKEN_URL",
    )
    google_oauth_revoke_url: str = Field(
        default="https://oauth2.googleapis.com/revoke",
        alias="GOOGLE_OAUTH_REVOKE_URL",
    )

    todoist_oauth_client_id: str = Field(default="", alias="TODOIST_OAUTH_CLIENT_ID")
    todoist_oauth_client_secret: str = Field(default="", alias="TODOIST_OAUTH_CLIENT_SECRET")
    todoist_oauth_authorize_url: str = Field(
        default="https://app.todoist.com/oauth/authorize",
        alias="TODOIST_OAUTH_AUTHORIZE_URL",
    )
    todoist_oauth_token_url: str = Field(
        default="https://api.todoist.com/oauth/access_token",
        alias="TODOIST_OAUTH_TOKEN_URL",
    )
    todoist_oauth_revoke_url: str = Field(
        default="https://api.todoist.com/sync/v9/access_tokens/revoke",
        alias="TODOIST_OAUTH_REVOKE_URL",
    )
    github_oauth_client_id: str = Field(default="", alias="GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str = Field(default="", alias="GITHUB_OAUTH_CLIENT_SECRET")
    github_oauth_authorize_url: str = Field(
        default="https://github.com/login/oauth/authorize",
        alias="GITHUB_OAUTH_AUTHORIZE_URL",
    )
    github_oauth_token_url: str = Field(
        default="https://github.com/login/oauth/access_token",
        alias="GITHUB_OAUTH_TOKEN_URL",
    )
    github_oauth_revoke_url: str = Field(default="", alias="GITHUB_OAUTH_REVOKE_URL")
    github_api_base_url: str = Field(default="https://api.github.com", alias="GITHUB_API_BASE_URL")
    email_transport: str = Field(default="mock", alias="EMAIL_TRANSPORT")
    email_from: str = Field(default="noreply@asya.local", alias="EMAIL_FROM")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    @property
    def vsellm_api_key_configured(self) -> bool:
        return bool(self.vsellm_api_key.strip())

    @property
    def frontend_dist_dir(self) -> Path:
        return Path(self.frontend_dist_path).resolve()

    @property
    def asya_db_url(self) -> str:
        explicit_url = self.database_url.strip()
        if explicit_url:
            self._validate_db_url(explicit_url)
            return explicit_url

        if self._has_postgres_env():
            return (
                "postgresql+psycopg://"
                f"{self.postgres_user}:{self.postgres_password}@"
                f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
                f"?sslmode={self.postgres_sslmode}"
            )

        db_path = self._resolve_sqlite_path(self.asya_db_path)
        if self.app_env.lower() == "production":
            raise ValueError(
                "Production environment requires DATABASE_URL or POSTGRES_* variables; "
                "SQLite fallback is allowed only for local/dev."
            )
        return f"sqlite+pysqlite:///{db_path.as_posix()}"

    @staticmethod
    def _resolve_sqlite_path(path: str) -> Path:
        db_path = Path(path)
        if not db_path.is_absolute():
            db_path = db_path.resolve()
        return db_path

    @staticmethod
    def _validate_db_url(db_url: str) -> None:
        lower = db_url.lower()
        if lower.startswith("sqlite") and "mode=memory" in lower:
            return

    def _has_postgres_env(self) -> bool:
        values = [
            self.postgres_host.strip(),
            self.postgres_db.strip(),
            self.postgres_user.strip(),
            self.postgres_password.strip(),
        ]
        return all(values)


@lru_cache
def get_settings() -> Settings:
    return Settings()
