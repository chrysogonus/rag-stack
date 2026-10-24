from alembic import context
from sqlalchemy import create_engine

from rag_stack.config import Settings

url = Settings().database_url.replace("postgresql://", "postgresql+psycopg://", 1)
with create_engine(url).connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
