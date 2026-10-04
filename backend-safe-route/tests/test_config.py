"""Validation and secret handling tests for environment settings."""

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings


def _settings_values() -> dict[str, str]:
    return {
        "db_user": "safe_route",
        "db_password": "test-database-password",
        "db_host": "localhost",
        "db_port": "5432",
        "db_name": "safe_route",
    }


def test_settings_validate_log_level_and_database_port() -> None:
    settings = Settings(
        **_settings_values(),
        log_level="debug",
    )

    assert settings.log_level == "DEBUG"
    assert settings.db_port == 5432

    with pytest.raises(ValidationError):
        Settings(**_settings_values(), log_level="VERBOSE")
    with pytest.raises(ValidationError):
        Settings(**{**_settings_values(), "db_port": "70000"})


def test_database_urls_disable_ssl_for_local_postgres() -> None:
    settings = Settings(**_settings_values(), db_ssl=False)

    assert settings.database_url == (
        "postgresql+asyncpg://safe_route:test-database-password@localhost:5432/safe_route"
    )
    assert settings.database_sync_url == (
        "postgresql://safe_route:test-database-password@localhost:5432/safe_route"
    )


def test_database_urls_require_ssl_by_default() -> None:
    settings = Settings(**_settings_values())

    assert settings.database_url.endswith("?ssl=require")
    assert settings.database_sync_url.endswith("?sslmode=require")


def test_sensitive_settings_are_masked_in_model_representation() -> None:
    settings = Settings(
        **_settings_values(),
        mapbox_secret_token="test-mapbox-token",
    )

    assert isinstance(settings.mapbox_secret_token, SecretStr)
    assert "test-mapbox-token" not in repr(settings)
    assert "test-database-password" not in repr(settings)
