title: Background Tasks
----

# Background Tasks

Proper includes a background task system built on [Huey](https://huey.readthedocs.io/). Tasks are defined as decorated functions and can execute immediately in development or be queued for asynchronous processing in production. The system supports multiple backends including in-memory, SQLite, SQL (via Peewee), and Redis.


## 1. Defining Tasks

Tasks live in the `tasks/` directory. Decorate any function with `@app.queue.task()` to make it a background task:

```python
# tasks/__init__.py
from ..main import app


@app.queue.task()
def send_welcome_email(user_id):
    from ..models import User
    user = User.get_by_id(user_id)
    # send the email...


@app.queue.task()
def generate_report(report_id):
    # long-running work...
    pass
```

Call the task like a normal function. In development, it runs immediately. In production, it's queued for a worker:

```python
send_welcome_email(user.id)
generate_report(report.id)
```

Arguments must be serializable (strings, numbers, dicts, lists). Don't pass model instances directly — pass IDs and look them up inside the task.

The generated app includes a built-in task for sending emails asynchronously:

```python
from proper.emails import EmailMessageDict
from ..main import app


@app.queue.task()
def send_email_task(message: EmailMessageDict):
    app.mailer.send_now(message)
```


## 2. Running Workers

In production, tasks are processed by a separate worker process. The generated `workers.py` file at the project root handles this:

```python
from huey.consumer import Consumer

from myapp.main import app


def get_config():
    return app.config.get("QUEUE_CONSUMER", {}).copy()


def run_consumer(config):
    if app.queue is None:
        raise RuntimeError("Queue not initialized.")
    print("Starting background workers...")
    consumer = Consumer(app.queue, **config)
    consumer.run()


if __name__ == "__main__":
    config = get_config()
    run_consumer(config)
```

Start the worker:

```bash
python workers.py
```

The worker reads the `QUEUE_CONSUMER` config to determine the number of workers, polling intervals, and other settings.


## 3. Configuration

Queue settings live in `config/storage.py`. There are two config dictionaries:

- `QUEUE` — the backend and its connection parameters
- `QUEUE_CONSUMER` — worker process settings

### 3.1 Queue Backend (`QUEUE`)

The `type` key specifies the Huey backend class. The remaining keys are passed to the constructor.

**MemoryHuey** (default — development):

```python
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}
```

With `immediate: True`, tasks execute synchronously when called. This is the default for development — no worker process needed.

**SqliteHuey** (file-based):

```python
QUEUE = {
    "type": "huey.SqliteHuey",
    "database": "storage/queue.sqlite3",
}
```

**RedisHuey** (production):

```python
QUEUE = {
    "type": "huey.RedisHuey",
    "name": "myapp",
}
```

Requires the `redis` package.

**SqlHuey** (SQL-based via Peewee):

```python
QUEUE = {
    "type": "huey.contrib.sql_huey.SqlHuey",
    "dbtype": "peewee.SqliteDatabase",
    "database": "storage/queue.sqlite3",
}
```

The `dbtype` key specifies a Peewee database class. The queue's database instance is registered as `app.db["proper_queue"]` for migration support.

### 3.2 Consumer Settings (`QUEUE_CONSUMER`)

```python
QUEUE_CONSUMER = {
    "workers": 1,                  # Number of worker threads/processes
    "periodic": True,              # Enable periodic task scheduler
    "initial_delay": 0.1,          # Queue polling interval (seconds)
    "backoff": 1.15,               # Backoff factor when queue is empty
    "max_delay": 10.0,             # Max interval between polls (seconds)
    "scheduler_interval": 1,       # Scheduler check interval (1-60 seconds)
    "worker_type": "thread",       # "thread", "process", or "greenlet"
    "check_worker_health": True,   # Monitor worker health
    "health_check_interval": 10,   # Health check frequency (seconds)
    "flush_locks": False,          # Flush locks on startup
    "extra_locks": "",             # Comma-separated extra lock names
}
```

All consumer settings have sensible defaults. You only need to override the ones you want to change.

### 3.3 Per-Environment Configuration

The generated config switches backends by environment:

```python
env = os.getenv("APP_ENV", "dev")

# Development (default)
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}

# Testing
if env == "test":
    QUEUE = {
        "type": "huey.MemoryHuey",
        "immediate": True,
        "immediate_use_memory": True,
    }

# Production
if env == "prod":
    QUEUE = {
        "type": "huey.RedisHuey",
        "name": "myapp",
    }
```


## 4. How It Works

### 4.1 Immediate Mode (Development)

When `immediate: True`, calling a task function executes it synchronously in the current process. No worker is needed. This is the default for development and testing.

### 4.2 Queued Mode (Production)

When `immediate` is not set or is `False`, calling a task function serializes the arguments and places a message on the queue. A separate worker process (started via `workers.py`) polls the queue and executes tasks.

### 4.3 Integration with the Framework

The queue is available as `app.queue` and is a standard [Huey](https://huey.readthedocs.io/) instance. You can use all of Huey's features:

```python
# Regular task
@app.queue.task()
def process_upload(file_id):
    pass

# Periodic task (runs on schedule)
@app.queue.periodic_task(crontab(minute="0", hour="*/2"))
def cleanup_expired_sessions():
    pass

# Task with retry
@app.queue.task(retries=3, retry_delay=60)
def call_external_api(url):
    pass
```

The framework also uses the queue internally. For example, the storage system queues image variant cleanup as background tasks, and the email system uses it for asynchronous sending via `send_later()`.


## 5. Database Migrations for SQL Backends

When using `SqlHuey`, the queue database requires its own migrations. The queue database is registered as `"proper_queue"` in `app.db`, and migration files live in `db/proper_queue/`.

The standard `proper db` commands work with the queue database:

```bash
proper db create "description" --db=proper_queue
proper db migrate --db=proper_queue
proper db rollback --db=proper_queue
```

The SqlHuey backend uses three tables: `queuekv` (key-value storage), `queueschedule` (scheduled tasks), and `queuetask` (task data).
