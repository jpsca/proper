from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "CACHE"
DEFAULT_CONFIG = {
    "type": "proper.cache.NoCache",
}

def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    validate_config(config)
    app.config[NAME] = config

    app.cache = cache = get_instance(**config)
    database = getattr(app.cache, "database", None)
    if database and database != ":memory:":
        app.db["proper_cache"] = database

    app.catalog.jinja_env.extend(app_cache=cache)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")
