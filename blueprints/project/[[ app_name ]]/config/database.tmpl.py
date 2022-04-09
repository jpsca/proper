import os

from proper import (
    Dot,
    is_development_env,
    is_testing_env,
    is_staging_or_production_env,
)


config = database_config = Dot()

config.dialect = None
config.name = None
config.host = None
config.port = None
config.user = None
config.password = None

config.engine_options = None
config.session_options = {"expire_on_commit": False}
config.migrations = "db/migrations"

if is_development_env:
    config.dialect = "sqlite+pysqlite"
    config.name = "db/[[ app_name ]].sqlite"
    # config.engine_options = {"echo": True}

elif is_staging_or_production_env:
    config.dialect = "postgresql"
    config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
    config.host = os.getenv("DATABASE_HOST", None)
    config.port = os.getenv("DATABASE_PORT", None)
    config.user = os.getenv("DATABASE_USER", None)
    config.password = os.getenv("DATABASE_PASSWORD", None)

elif is_testing_env:
    config.dialect = "sqlite+pysqlite"
    config.name = "db/[[ app_name ]]-test.sqlite"
