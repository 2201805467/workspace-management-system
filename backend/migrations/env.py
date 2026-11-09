from alembic import context

from app.db import Base, get_engine
from app import models  # noqa: F401: register table metadata


def run():
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run()
