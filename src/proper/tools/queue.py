import structlog

from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "QUEUE"
NAME_CONSUMER = "QUEUE_CONSUMER"
# The keyword argument that takes the request ID to the task
REQUEST_ID_KWARG = "_proper_request_id"

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
    # Seconds to wait for running tasks on a graceful shutdown; `None` waits.
    "shutdown_timeout": None,
    # Signal that starts a graceful shutdown: "INT" (ctrl+c) or "TERM", which
    # is what `docker stop` and most supervisors send.
    "graceful_signal": "INT",
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
        if config.get("filename") == ":memory:":
            # A ":memory:" SQLite database is private to each connection, and
            # SqliteHuey opens a separate connection per worker thread - and the
            # consumer normally runs in its own process. So nothing would share
            # the same queue. (Shared-cache can't help: in-memory databases are
            # only shared within a single process.)
            raise ConfigError(
                "SqliteHuey cannot use ':memory:' (the queue would not be "
                "shared with the consumer process). Use a file path, "
                "RedisHuey, or MemoryHuey for an in-memory queue."
            )

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
    pass_the_request_id(app.queue)


def pass_the_request_id(queue):
    """Log the lines of a task with the ID of the request that enqueued it.

    When a task is enqueued while a request is being answered, the ID goes
    with the task (and with the ones it is chained to) as a keyword
    argument. The worker takes it out before calling the function, binds it
    with `structlog.contextvars` while the task runs, and puts it back in
    case the task is retried.
    """
    # Here, not at the top: importing huey imports redis
    from huey.signals import SIGNAL_ENQUEUED

    @queue.signal(SIGNAL_ENQUEUED)
    def add_the_request_id(_signal, task, *_args):
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id is None:
            return
        tasks = [task]
        while tasks:
            task = tasks.pop()
            if task is None or REQUEST_ID_KWARG in task.kwargs:
                continue
            task.kwargs[REQUEST_ID_KWARG] = request_id
            tasks += [task.on_complete, task.on_error]

    @queue.pre_execute(name="proper_bind_request_id")
    def bind_the_request_id(task):
        request_id = task.kwargs.pop(REQUEST_ID_KWARG, None)
        if request_id is not None:
            task._proper_request_id = request_id
            task._proper_tokens = structlog.contextvars.bind_contextvars(
                request_id=request_id
            )

    @queue.post_execute(name="proper_unbind_request_id")
    def unbind_the_request_id(task, _value, _exception):
        tokens = task.__dict__.pop("_proper_tokens", None)
        if tokens is not None:
            structlog.contextvars.reset_contextvars(**tokens)
            task.kwargs[REQUEST_ID_KWARG] = task.__dict__.pop("_proper_request_id")


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
