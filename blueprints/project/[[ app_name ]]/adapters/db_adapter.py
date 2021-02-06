from sqla_wrapper import SQLAlchemy

from ..config import config


db = SQLAlchemy(config.database.uri, echo=False)
