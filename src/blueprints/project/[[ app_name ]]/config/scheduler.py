from proper import env, PROD

from .storage import *  # noqa


# If True, run synchronously and ignore the SCHEDULER,
# SCHEDULER_CONNECTIONS, and SCHEDULER_CONSUMER settings.
SCHEDULER_IMMEDIATE: bool = env != PROD

SCHEDULER_CONNECTIONS = {
    "redis": {
        "type": "RedisHuey",
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "user": REDIS_USER,
        "password": REDIS_PASSWORD,
        "db": REDIS_DB,
        # Definitely you should use pooling
        "connection_pool": None,
        # If not polling (blocking pop), use timeout
        "read_timeout": 1,
        # Allow Redis config via a DSN
        "url": None,
    },
    "sqlite": {
        "type": " SqliteHuey",
        "filename": "db/huey.db",
    },
}

SCHEDULER: str = "sqlite"

SCHEDULER_CONSUMER = {
    "workers": 1,
    "worker_type": "thread",
    # Smallest polling interval
    "initial_delay": 0.1,
    # Exponential backoff using this rate
    "backoff": 1.15,
    # Max possible polling interval
    "max_delay": 10.0,
    # Check schedule every second
    "scheduler_interval": 1,
    # Enable crontab feature
    "periodic": True,
    # Enable worker health checks
    "check_worker_health": True,
    # Check worker health every second
    "health_check_interval": 1,
}

# Store return values of tasks
SCHEDULER_RESULTS: bool = True
# If a task returns None, do not save to results
SCHEDULER_STORE_NONE: bool = False
# Use UTC for all times internally
SCHEDULER_UTC: bool = True
# Perform blocking pop rather than poll Redis
SCHEDULER_BLOCKING: bool = True
