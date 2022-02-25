from .shared import config


config.debug = True
config.secret_key = "---- This is a fake secret key just for development ----"

config.database.dialect = "sqlite+pysqlite"
config.database.name = "db/[[ app_name ]].sqlite"
config.database.host = None
config.database.user = None
# config.database.engine_options = {"echo": True}
