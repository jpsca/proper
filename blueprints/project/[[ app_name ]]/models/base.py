from sqla_wrapper import Alembic, SQLAlchemy

from ..config import config


__all__ = ("Base", "alembic", "db", "db")

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
alembic = Alembic(db, config.alembic_migrations)


class Base(db.Model):
    __abstract__ = True

    def __repr__(self):
        return f"{self.__class__.__name__} #{self.id}"
