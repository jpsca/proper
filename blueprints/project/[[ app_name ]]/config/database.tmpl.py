import os

from proper import (
    Dot,
    is_development_env,
    is_testing_env,
    is_staging_or_production_env,
)


database_config = Dot()

database_config.dialect = None
database_config.name = None
database_config.host = None
database_config.port = None
database_config.user = None
database_config.password = None

database_config.engine_options = None
database_config.session_options = {"expire_on_commit": False}
database_config.migrations = "db/migrations"

if is_development_env:
    database_config.dialect = "sqlite+pysqlite"
    database_config.name = "db/[[ app_name ]].sqlite"
    # database_config.engine_options = {"echo": True}

elif is_staging_or_production_env:
    database_config.dialect = "postgresql"
    database_config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
    database_config.host = os.getenv("DATABASE_HOST", None)
    database_config.port = os.getenv("DATABASE_PORT", None)
    database_config.user = os.getenv("DATABASE_USER", None)
    database_config.password = os.getenv("DATABASE_PASSWORD", None)

elif is_testing_env:
    database_config.dialect = "sqlite+pysqlite"
    database_config.name = "db/[[ app_name ]]-test.sqlite"
