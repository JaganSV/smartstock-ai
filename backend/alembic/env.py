"""Alembic environment. The database URL comes from application settings."""

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings

config = context.config

# No models yet (P0); autogenerate metadata is introduced in P1.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().sqlalchemy_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_settings().sqlalchemy_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
