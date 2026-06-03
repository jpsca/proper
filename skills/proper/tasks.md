---
title: Background Tasks
description: Huey task queue — task definition, scheduling, retries, pipelines, worker config
last_verified: 2026-06-03
---

# Background Tasks

Proper includes a background task system built on [Huey](https://huey.readthedocs.io/). Tasks are defined as decorated functions and execute immediately in development or are queued for asynchronous processing in production. The queue is available as `app.queue` — a standard Huey instance — so all of Huey's features work directly.

## Table of Contents

- [Defining Tasks](#defining-tasks)
- [Periodic Tasks](#periodic-tasks)
- [Scheduling Tasks](#scheduling-tasks)
- [Retries and Error Handling](#retries-and-error-handling)
- [Results](#results)
- [Revoking (Canceling) Tasks](#revoking-canceling-tasks)
- [Task Locking](#task-locking)
- [Task Pipelines](#task-pipelines)
- [Running Workers](#running-workers)
- [Configuration](#configuration)
- [Hooks and Signals](#hooks-and-signals)
- [Context Tasks](#context-tasks)
- [Key/Value Storage](#keyvalue-storage)
- [Database Migrations for SQL Backends](#database-migrations-for-sql-backends)
- [Exceptions](#exceptions)


## Defining Tasks

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

Call the task like a normal function. In development (immediate mode), it runs synchronously. In production, it's queued for a worker and returns a `Result` handle:

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

The framework also uses the queue internally — the storage system queues image variant cleanup, and the email system uses it for `send_later()`.


### `task()` Decorator Options

```python
@app.queue.task(retries=0, retry_delay=0, context=False, name=None, expires=None)
def my_task(arg1, arg2):
    return result
```

| Parameter     | Description                                                                  |
|---------------|------------------------------------------------------------------------------|
| `retries`     | Number of automatic retries on failure                                       |
| `retry_delay` | Seconds to wait between retries                                              |
| `context`     | Pass the `Task` instance as `task` kwarg                                     |
| `name`        | Custom task name (default: module.function)                                  |
| `expires`     | Discard if not run within this time (int seconds, timedelta, or datetime)    |

### Priority (PriorityRedisHuey only)

If the queue backend is `PriorityRedisHuey`, tasks accept a `priority` kwarg at enqueue time. Higher numbers run first:

```python
my_task(arg1, arg2, priority=50)
my_task.schedule(args=(1, 2), delay=60, priority=50)
```

Other backends (the default `MemoryHuey`, `SqliteHuey`, plain `RedisHuey`) ignore `priority` — switch the queue type in config if you need it.


## Periodic Tasks

Use `@app.queue.periodic_task()` with a `crontab()` schedule for recurring work. Periodic tasks take no arguments and their return values are discarded:

```python
from huey import crontab

@app.queue.periodic_task(crontab(minute="0", hour="*/2"))
def cleanup_expired_sessions():
    pass
```

Accepts the same kwargs as `task()` (`retries`, `retry_delay`, etc.) plus the `validate_datetime` function (typically `crontab()`).

### `crontab()` Syntax

```python
crontab(minute='*', hour='*', day='*', month='*', day_of_week='*')
```

| Syntax | Meaning                       |
|--------|-------------------------------|
| `*`    | Every value                   |
| `*/n`  | Every n intervals             |
| `m-n`  | Range m through n inclusive   |
| `m,n`  | Specific values m and n       |

`day_of_week`: 0=Sunday, 6=Saturday. Minimum granularity is 1 minute.

```python
crontab(minute='*/10', hour='9-17')  # Every 10 min during business hours
crontab(minute='0', hour='3')         # Daily at 3am
crontab(minute='0,30')                # Every half hour
```


## Scheduling Tasks

Enqueue a task to run after a delay or at a specific time:

```python
# Run after a delay (seconds)
res = my_task.schedule(args=(1, 2), delay=60)

# Run at a specific time
from datetime import datetime, timedelta
eta = datetime.now() + timedelta(hours=1)
res = my_task.schedule(args=(1, 2), eta=eta)
```


## Retries and Error Handling

### Automatic Retries

```python
@app.queue.task(retries=3, retry_delay=60)
def flaky_task(url):
    return fetch(url)
```

### Explicit Retry

Force a retry from within a task, regardless of retry config:

```python
from huey import RetryTask

@app.queue.task()
def fetch_data(url):
    try:
        return urlopen(url)
    except HTTPError:
        raise RetryTask(delay=60)
```

### Canceling Execution

Control retry behavior when canceling:

```python
from huey import CancelExecution

@app.queue.task(retries=3)
def conditional_task():
    if fatal_error():
        raise CancelExecution(retry=False)  # Never retry
    if temporary_error():
        raise CancelExecution(retry=True)   # Always retry
    if maybe_retry():
        raise CancelExecution()  # Retry only if retries remain
```

### Task Expiration

Discard tasks that sit in the queue too long:

```python
@app.queue.task(expires=60)  # Must run within 60s of being enqueued
def time_sensitive():
    pass

# Per-invocation override
time_sensitive(expires=timedelta(minutes=5))
```


## Results

Calling a task in queued mode returns a `Result` handle:

```python
res = my_task(1, 2)
res()                          # Returns result or None if not ready
res(blocking=True)             # Block until result is ready
res(blocking=True, timeout=5)  # Block up to 5 seconds, raises ResultTimeout
res.get(preserve=True)         # Read result without deleting it from store
```

| Method / Property              | Description                                            |
|--------------------------------|--------------------------------------------------------|
| `res()` / `res.get(**kw)`     | Fetch result. Returns `None` if not ready              |
| `res.id`                       | Unique task ID                                         |
| `res.revoke()`                 | Cancel task (if not yet running)                       |
| `res.restore()`                | Un-cancel a revoked task                               |
| `res.is_revoked()`             | Check if task is revoked                               |
| `res.reschedule(eta=, delay=)` | Reschedule task                                        |
| `res.reset()`                  | Clear cached result (for re-reading after retry)       |

If a task raises an exception, `res()` raises `TaskException` wrapping the original error.

By default, results are deleted after first read. Use `preserve=True` to keep them.


## Revoking (Canceling) Tasks

```python
# Cancel a specific task instance
res = my_task(1, 2)
res.revoke()

# Cancel ALL instances of a task
my_task.revoke()
my_task.restore()

# Skip just the next execution of a periodic task
send_emails.revoke(revoke_once=True)

# Pause a periodic task for 3 hours
from datetime import datetime, timedelta
send_emails.revoke(revoke_until=datetime.now() + timedelta(hours=3))
```


## Task Locking

Prevents concurrent execution of the same task:

```python
# As decorator (place AFTER @task)
@app.queue.periodic_task(crontab(minute='*/5'))
@app.queue.lock_task('report-lock')
def generate_report():
    run_report()

# As context manager
@app.queue.task()
def backup():
    do_code_backup()
    with app.queue.lock_task('db-backup'):
        do_db_backup()
```

If the lock can't be acquired, `TaskLockedException` is raised and the task is skipped (retried if configured).


## Task Pipelines

Chain tasks so each receives the previous task's return value:

```python
@app.queue.task()
def add(a, b):
    return a + b

pipeline = (add.s(1, 2)       # Task representing add(1, 2)
            .then(add, 3)      # add(result, 3)
            .then(add, 4))     # add(result, 4)

result_group = app.queue.enqueue(pipeline)
result_group.get(blocking=True)  # [3, 6, 10]
```

- If a task returns a `tuple`, it's unpacked as `*args` for the next task
- If a task returns a `dict`, it's used as `**kwargs` for the next task
- `Task.error(task, *args)` chains a task that runs only on failure

### Map

Apply a task to multiple argument sets:

```python
result_group = add.map([(1, 2), (3, 4), (5, 6)])
result_group.get(blocking=True)  # [3, 7, 11]
```


## Running Workers

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


## Configuration

Queue settings live in `config/storage.py`. There are two config dictionaries:

- `QUEUE` — the backend and its connection parameters
- `QUEUE_CONSUMER` — worker process settings

### Queue Backend (`QUEUE`)

The `type` key specifies the Huey backend class. The remaining keys are passed to the constructor.

**MemoryHuey** (default — development):

```python
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}
```

With `immediate: True`, tasks execute synchronously when called — no worker process needed. This is the default for development and testing.

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

### Consumer Settings (`QUEUE_CONSUMER`)

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

### Per-Environment Configuration

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


## Hooks and Signals

### Startup Hook

```python
@app.queue.on_startup()
def setup():
    # Runs once per worker when it starts
    pass
```

### Pre/Post Execute Hooks

```python
from huey import CancelExecution

@app.queue.pre_execute()
def before_task(task):
    if should_skip():
        raise CancelExecution()

@app.queue.post_execute()
def after_task(task, task_value, exc):
    if exc is not None:
        log_error(task.id, exc)
```

### Signals

Signal handlers run synchronously in the consumer:

```python
from huey.signals import SIGNAL_ERROR, SIGNAL_COMPLETE

@app.queue.signal(SIGNAL_ERROR)
def on_error(signal, task, exc=None):
    notify_admin(task.id, exc)

@app.queue.signal()  # All signals
def on_any(signal, task, exc=None):
    log(signal, task.id)
```

**Available signals:** `SIGNAL_CANCELED`, `SIGNAL_COMPLETE`, `SIGNAL_ENQUEUED`, `SIGNAL_ERROR`, `SIGNAL_EXECUTING`, `SIGNAL_EXPIRED`, `SIGNAL_LOCKED`, `SIGNAL_RETRYING`, `SIGNAL_REVOKED`, `SIGNAL_SCHEDULED`, `SIGNAL_INTERRUPTED`.

Disconnect with `app.queue.disconnect_signal(handler)`.


## Context Tasks

Wrap a task in a context manager (e.g., for database connections in the worker):

```python
@app.queue.context_task(db)
def query_task(n):
    # db connection is automatically opened/closed
    return do_something(n)
```


## Key/Value Storage

The result store can be used directly for arbitrary data:

```python
app.queue.put('my-key', data)
app.queue.get('my-key', peek=True)  # peek=True preserves the value
```


## Database Migrations for SQL Backends

When using `SqlHuey`, the queue database requires its own migrations. The queue database is registered as `"proper_queue"` in `app.db`, and migration files live in `db/proper_queue/`.

The standard `proper db` commands work with the queue database:

```bash
proper db create "description" --db=proper_queue
proper db migrate --db=proper_queue
proper db rollback --db=proper_queue
```

The SqlHuey backend uses three tables: `queuekv` (key-value storage), `queueschedule` (scheduled tasks), and `queuetask` (task data).


## Exceptions

| Exception              | Description                                                        |
|------------------------|--------------------------------------------------------------------|
| `TaskException`        | Wraps exceptions from failed tasks (raised when reading result)    |
| `ResultTimeout`        | `res(blocking=True, timeout=N)` timed out                         |
| `TaskLockedException`  | Lock could not be acquired                                         |
| `CancelExecution`      | Raised in task or pre-execute hook to cancel                       |
| `RetryTask(delay=N)`   | Force retry regardless of retry config                             |
