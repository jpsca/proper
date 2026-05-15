from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "QUEUE"
NAME_CONSUMER = "QUEUE_CONSUMER"

DEFAULT_CONFIG = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}
DEFAULT_CONSUMER_CONFIG = {
    # Number of workers to spawn.
    "workers": 1,
    # Enable periodic task scheduler?
    "periodic": True,
    # Default queue polling interval.
    "initial_delay": 0.1,
    # Exponential backoff factor when queue empty.
    "backoff": 1.15,
    # Maximum interval between polling events.
    "max_delay": 10.0,
    # Interval for the scheduler. Must be between 1 and 60s
    "scheduler_interval": 1,
    # Type of worker to use ("thread", "process", or "greenlet").
    "worker_type": "thread",
    # Whether to check worker health.
    "check_worker_health": True,
    # Interval for health checks.
    "health_check_interval": 10,
    # Whether to flush locks.
    "flush_locks": False,
    # Comma-separated extra locks to use.
    "extra_locks": "",
}


def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    validate_config(config)
    app.config[NAME] = config

    consumer_config = {**DEFAULT_CONSUMER_CONFIG, **app.config.get(NAME_CONSUMER, {})}
    validate_consumer_config(consumer_config)
    app.config[NAME_CONSUMER] = consumer_config

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
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")

    if "dbtype" in config:
        if not isinstance(config["dbtype"], (str | type)):
            raise ConfigError(f"{NAME}['dbtype'] must be a string or a class")


def validate_consumer_config(config):
    pass
