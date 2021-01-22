from sqla_wrapper import SQLAlchemy

from [[ name ]].config import config


db = SQLAlchemy(config.database.uri, echo=False)
