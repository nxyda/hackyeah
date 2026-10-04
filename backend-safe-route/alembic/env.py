from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database.base import DatabaseBase
import app.models


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_sync_url)
target_metadata = DatabaseBase.metadata


def include_object(
    object_,
    name,
    type_,
    reflected,
    compare_to,
):
    """Nie generuje ponownie indeksów zarządzanych poza metadanymi modeli."""

    if type_ == "index" and name and name.startswith("idx_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Uruchamia migracje bez otwierania połączenia."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Uruchamia migracje przez synchroniczne połączenie psycopg."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
