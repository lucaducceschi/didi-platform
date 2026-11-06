from alembic import context

from backend.app.database import Base, get_engine

target_metadata = Base.metadata


def run_migrations() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Offline migrations are not supported.")
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
