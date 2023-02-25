import os

from proper import DotDict


database_config = DotDict()

database_config.name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
database_config.host = os.getenv("DATABASE_HOST", None)
database_config.port = os.getenv("DATABASE_PORT", None)
database_config.user = os.getenv("DATABASE_USER", None)
database_config.password = os.getenv("DATABASE_PASSWORD", None)
