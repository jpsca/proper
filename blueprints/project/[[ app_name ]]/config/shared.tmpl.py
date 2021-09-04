import os


debug = False
host = ""

auth_hash_name = "argon2"
auth_rounds = None
auth_password_minlen = 9
auth_password_maxlen = 1024
auth_token_life = 10800  # 3 hours

mailer_default_from = "hello@example.com"

session_cookie_name = "_session"
session_cookie_httponly = True
session_cookie_secure = False

database_dialect = "postgresql"
database_name = os.getenv("DATABASE_NAME", "[[ app_name ]]")
database_user = os.getenv("DATABASE_USER")
database_password = os.getenv("DATABASE_PASSWORD")
database_host = os.getenv("DATABASE_HOST")
database_port = os.getenv("DATABASE_PORT")
database_engine_options = None

alembic_migrations = "db/migrations"
