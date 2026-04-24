from functools import lru_cache

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

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def vsellm_api_key_configured(self) -> bool:
        return bool(self.vsellm_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
