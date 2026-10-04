from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from sqlalchemy.engine import URL

from pydantic_settings import BaseSettings, SettingsConfigDict


LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class Settings(BaseSettings):
    """Ustawienia środowiska wymagane przez aplikację."""

    api_mode: Literal["mock", "live"] = "live"
    log_level: LogLevel = "INFO"
    mapbox_secret_token: SecretStr = SecretStr("")
    jwt_secret_key: SecretStr = SecretStr("")
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    jwt_issuer: str = "safe-route-api"
    admin_session_secret: SecretStr = SecretStr("")
    admin_cookie_secure: bool = True
    google_client_id: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: SecretStr = SecretStr("")
    facebook_graph_api_version: str = "v23.0"
    routing_corridor_buffer_m: float = Field(default=250.0, gt=0, le=5_000)

    # Zmienne bazy danych (Pydantic automatycznie zaczyta je z pliku .env np. z kluczy db_user, db_password)
    db_user: str
    db_password: SecretStr
    db_host: str
    db_port: int = Field(ge=1, le=65_535)
    db_name: str
    db_ssl: bool = True

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value

    @property
    def database_url(self) -> str:
        """Dynamicznie buduje URL bazy danych na podstawie zmiennych środowiskowych."""
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"ssl": "require"} if self.db_ssl else {},
        ).render_as_string(hide_password=False)

    @property
    def database_sync_url(self) -> str:
        """Buduje connection string dla synchronicznych narzędzi administracyjnych."""
        return URL.create(
            "postgresql",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"sslmode": "require"} if self.db_ssl else {},
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Zwraca cache'owaną konfigurację aplikacji."""
    return Settings()
