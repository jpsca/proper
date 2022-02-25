from .development import config


config.debug = False
config.secret_key = "---- This is a fake secret key just for testing ----"

config.database.dialect = "sqlite+pysqlite"
config.database.name = "db/[[ app_name ]]-test.sqlite"
config.database.host = None
config.database.user = None
