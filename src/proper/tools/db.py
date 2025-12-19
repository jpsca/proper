from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "DATABASES"
DEFAULT_CONFIG = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": ":memory:",
    },
}


def setup(app):
    db = {}
    config = app.config.get(NAME, DEFAULT_CONFIG)
    validate_config(config)
    app.config[NAME] = config

    for name, db_config in config.items():
        if db_config is None:
            continue
        db[name] = get_instance(**db_config)

    app.db = db


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    for name, db_config in config.items():
        if not db_config:
            continue
        if not isinstance(db_config, dict):
            raise ConfigError(
                f"{NAME}['{name}'] config must be a dictionary or None"
            )

        if "type" not in db_config:
            raise ConfigError(f"{NAME}['{name}'] config must have a 'type' key")
        if not isinstance(db_config["type"], (str | type)):
            raise ConfigError(f"{NAME}['{name}']['type'] must be a string or a class")

        if "database" not in db_config:
            raise ConfigError(f"{NAME}['{name}'] config must have a 'database' key")

        if not isinstance(db_config["database"], str):
            raise ConfigError(f"{NAME}['{name}']['database'] must be a string")
