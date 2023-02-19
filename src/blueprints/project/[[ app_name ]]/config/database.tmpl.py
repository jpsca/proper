import os

from proper import (
    Dot,
    is_development_env,
    is_testing_env,
    is_staging_or_production_env,
)


database_config = Dot()

database_config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
database_config.host = os.getenv("DATABASE_HOST", None)
database_config.port = os.getenv("DATABASE_PORT", None)
database_config.user = os.getenv("DATABASE_USER", None)
database_config.password = os.getenv("DATABASE_PASSWORD", None)

