import os


config = {
    "engines": {
        "sqlite": {
            "engine": "sqlite",
            "path": "db/sqlite.db",
            "pragmas": {},
        },
        "postgres": {
            "engine": "postgres",
            "name": os.getenv("DB_NAME", "[[ app_name ]]"),
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
        },
        "mysql": {
            "engine": "mysql",
            "name": os.getenv("DB_NAME", "[[ app_name ]]"),
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
        },
    },

    "default": "postgres",
}
