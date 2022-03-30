from proper import Dot, get_env


env = get_env()

config = Dot()
config.type = "redis"
# If True, run synchronously and ignore the type above
config.immediate = env not in ("production", "staging")

config.results = True  # Store return values of tasks
config.store_none = False  # If a task returns None, do not save to results
config.utc = True  # Use UTC for all times internally
config.blocking = True  # Perform blocking pop rather than poll Redis

config.connection = Dot()
config.connection.host = "localhost"
config.connection.port = 6379
config.connection.db = 0
config.connection.connection_pool = None  # Definitely you should use pooling
config.connection.read_timeout = 1  # If not polling (blocking pop), use timeout
config.connection.url = None  # Allow Redis config via a DSN

config.consumer = Dot()
config.consumer.workers = 1
config.consumer.worker_type = "thread"
config.consumer.initial_delay = 0.1  # Smallest polling interval
config.consumer.backoff = 1.15  # Exponential backoff using this rate
config.consumer.max_delay = 10.0  # Max possible polling interval
config.consumer.scheduler_interval = 1  # Check schedule every second
config.consumer.periodic = True  # Enable crontab feature
config.consumer.check_worker_health = True  # Enable worker health checks
config.consumer.health_check_interval = 1  # Check worker health every second
