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
    sqlite_path: str = Field(default="./data/asya.sqlite3", alias="SQLITE_PATH")
    asya_db_path: str = Field(default="./data/asya-0.2.sqlite3", alias="ASYA_DB_PATH")
    tmp_dir: str = Field(default="./tmp", alias="TMP_DIR")
    max_files_per_message: int = Field(default=10, alias="MAX_FILES_PER_MESSAGE")
    max_file_size_mb: int = Field(default=256, alias="MAX_FILE_SIZE_MB")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    serve_frontend: bool = Field(default=True, alias="SERVE_FRONTEND")
    frontend_dist_path: str = Field(default="../frontend/dist", alias="FRONTEND_DIST_PATH")
    auth_registration_mode: str = Field(default="open", alias="AUTH_REGISTRATION_MODE")
    auth_cookie_name: str = Field(default="asya_session", alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_session_ttl_hours: int = Field(default=168, alias="AUTH_SESSION_TTL_HOURS")
    auth_session_hash_secret: str = Field(default="dev-change-me", alias="AUTH_SESSION_HASH_SECRET")
    master_encryption_key: str = Field(default="", alias="MASTER_ENCRYPTION_KEY")
    memory_extraction_enabled: bool = Field(default=True, alias="MEMORY_EXTRACTION_ENABLED")
    oauth_state_ttl_seconds: int = Field(default=900, alias="OAUTH_STATE_TTL_SECONDS")

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

    @property
    def vsellm_api_key_configured(self) -> bool:
        return bool(self.vsellm_api_key.strip())

    @property
    def frontend_dist_dir(self) -> Path:
        return Path(self.frontend_dist_path).resolve()

    @property
    def asya_db_url(self) -> str:
        db_path = Path(self.asya_db_path)
        if not db_path.is_absolute():
            db_path = db_path.resolve()
        return f"sqlite+pysqlite:///{db_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
