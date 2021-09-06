from sqla_wrapper import Alembic, SQLAlchemy
from sqlalchemy.orm import scoped_session

from ..config import config


__all__ = ("Base", "alembic", "db", "dbs")

db = SQLAlchemy(
    dialect=config.database_dialect,
    name=config.database_name,
    user=config.database_user,
    password=config.database_password,
    host=config.database_host,
    port=config.database_port,
    engine_options=config.database_engine_options,
    session_options={"expire_on_commit": False}
)
dbs = scoped_session(db.Session)()

alembic = Alembic(db, config.alembic_migrations)


class Base(db.Model):
    __abstract__ = True
