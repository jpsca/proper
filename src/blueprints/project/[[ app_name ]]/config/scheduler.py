from proper import is_staging_or_production_env

from .storage import redis


config = {
    # If True, run synchronously and ignore the type above
    "immediate": not is_staging_or_production_env,
    # Store return values of tasks
    "results": True,
    # If a task returns None, do not save to results
    "store_none": False,
    # Use UTC for all times internally
    "utc": True,
    # Perform blocking pop rather than poll Redis
    "blocking": True,

    "type": "RedisHuey",
    "connection": {
        "host": redis["host"],
        "port": redis["port"],
        "user": redis["user"],
        "password": redis["password"],
        "db": redis["db"],
        # Definitely you should use pooling
        "connection_pool": None,
        # If not polling (blocking pop), use timeout
        "read_timeout": 1,
        # Allow Redis config via a DSN
        "url": None,
    },

    "consumer": {
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
    },
}
