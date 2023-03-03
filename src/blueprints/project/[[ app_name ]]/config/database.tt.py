import os

from proper import DotDict


database_config = DotDict()

database_config.engine = os.getenv("DATABASE_ENGINE", "sqlite")
# database_config.engine = os.getenv("DATABASE_ENGINE", "postgres")

database_config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
database_config.host = os.getenv("DATABASE_HOST", "localhost")
database_config.port = os.getenv("DATABASE_PORT", 5432)
database_config.user = os.getenv("DATABASE_USER", "postgres")
database_config.password = os.getenv("DATABASE_PASSWORD", "postgres")
