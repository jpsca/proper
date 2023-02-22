from proper import DotDict, is_staging_or_production_env


scheduler_config = DotDict()

scheduler_config.type = "redis"
# If True, run synchronously and ignore the type above
scheduler_config.immediate = not is_staging_or_production_env

scheduler_config.results = True  # Store return values of tasks
scheduler_config.store_none = False  # If a task returns None, do not save to results
scheduler_config.utc = True  # Use UTC for all times internally
scheduler_config.blocking = True  # Perform blocking pop rather than poll Redis

connection = DotDict()
connection.host = "localhost"
connection.port = 6379
connection.db = 0
connection.connection_pool = None  # Definitely you should use pooling
connection.read_timeout = 1  # If not polling (blocking pop), use timeout
connection.url = None  # Allow Redis config via a DSN
scheduler_config.connection = connection

consumer = DotDict()
consumer.workers = 1
consumer.worker_type = "thread"
consumer.initial_delay = 0.1  # Smallest polling interval
consumer.backoff = 1.15  # Exponential backoff using this rate
consumer.max_delay = 10.0  # Max possible polling interval
consumer.scheduler_interval = 1  # Check schedule every second
consumer.periodic = True  # Enable crontab feature
consumer.check_worker_health = True  # Enable worker health checks
consumer.health_check_interval = 1  # Check worker health every second
scheduler_config.consumer = consumer
