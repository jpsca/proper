from proper.helpers.utils import get_instance


NAME = "QUEUE"
NAME_CONSUMER = "QUEUE_CONSUMER"

DEFAULT_CONFIG = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}
DEFAULT_CONSUMER_CONFIG = {}


def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    validate_config(config)
    app.config[NAME] = config

    app.config.setdefault(NAME_CONSUMER, DEFAULT_CONSUMER_CONFIG)
    validate_consumer_config(app.config[NAME_CONSUMER])

    if config["type"] == "huey.SqliteHuey":
        if "database" in config:
            config["filename"] = config.pop("database")

    elif config["type"] == "huey.contrib.sql_huey.SqlHuey":
        if "dbtype" in config:
            config["database"] = get_instance(
                type=config.pop("dbtype"),
                database=config.pop("database", None),
                host=config.pop("host", None),
                port=config.pop("port", None),
                user=config.pop("user", None),
                password=config.pop("password", None),
            )
            app.db["proper_queue"] = config["database"]

    app.queue = get_instance(**config)


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ValueError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ValueError(f"{NAME}['type'] must be a string or a class")

    if "dbtype" in config:
        if not isinstance(config["dbtype"], (str | type)):
            raise ValueError(f"{NAME}['dbtype'] must be a string or a class")


def validate_consumer_config(config):
    pass
