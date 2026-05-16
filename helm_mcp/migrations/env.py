"""Local-dev alembic env for the MCP plugin.

Used only when a plugin author runs ``alembic`` from this directory. The Helm
installer drives migrations via ``app.plugins._migration_runner`` instead.

Version state tracked in ``alembic_version_helm_mcp``.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.config import settings  # noqa: E402
from helm_mcp.models import Base  # noqa: E402

PLUGIN_NAME = "helm-mcp"
VERSION_TABLE = f"alembic_version_{PLUGIN_NAME.replace('-', '_')}"

config = context.config
config.set_main_option("sqlalchemy.url", settings.db_url.replace("+asyncpg", ""))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


run_migrations_online()
