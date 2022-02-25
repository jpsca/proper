import os

from proper import Dot, get_env


env = get_env()
config = Dot()

config.dialect = None
config.name = None
config.host = None
config.port = None
config.user = None
config.password = None

config.engine_options = None
config.session_options = {"expire_on_commit": False}
config.migrations = "db/migrations"

if env == "development":
    config.dialect = "sqlite+pysqlite"
    config.name = "db/[[ app_name ]].sqlite"
    # config.engine_options = {"echo": True}

elif env in ("production", "staging"):
    config.dialect = "postgresql"
    config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
    config.host = os.getenv("DATABASE_HOST", None)
    config.port = os.getenv("DATABASE_PORT", None)
    config.user = os.getenv("DATABASE_USER", None)
    config.password = os.getenv("DATABASE_PASSWORD", None)

elif env == "testing":
    config.dialect = "sqlite+pysqlite"
    config.name = "db/[[ app_name ]]-test.sqlite"
