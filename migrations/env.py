"""Alembic environment: which database to migrate and which models to compare with.

The database is the same one the app uses: DATABASE_URL from the environment/.env.
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is missing. Set it in .env or the environment.")
url = url.replace("postgres://", "postgresql://", 1)

# importing the models registers every table on Base.metadata
from backend.db.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Write the SQL instead of running it (alembic upgrade head --sql)."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
