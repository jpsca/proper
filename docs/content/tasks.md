---
title: Background Tasks
description: |
  How to move slow work out of the request cycle in Proper. Covers defining tasks, enqueuing and scheduling them, periodic tasks, retries, reading results, running the worker process, and configuring the queue backend.
number_headers: true
---

# Background Tasks

Some work doesn't belong in a web request. Sending an email, generating a PDF, resizing an image, calling a slow third-party API - if the user has to wait for it, the page hangs and a timeout or a dropped connection takes the work down with it. The fix is to hand that work to a *background task*: the request returns immediately, and the slow part runs somewhere else.

This guide covers how to write that "somewhere else" in Proper.

After reading this guide, you will know:

- What the queue, a task, and the worker are, and how they fit together.
- How to define a task and call it from a controller.
- How to schedule a task for later or run one on a recurring schedule.
- How to retry failing tasks and read their results.
- How to run the worker process in development and in production.
- How to pick and configure a queue backend for each environment.
- How to test code that enqueues tasks.

---

## Huey

Proper's background task system is [Huey](https://huey.readthedocs.io/){target=_blank}, a small task queue library, exposed directly. There is no Proper-specific task API to learn: `app.queue` *is* a Huey instance, so everything in Huey's documentation works as written. Proper's contribution is the wiring - loading the config, giving you a `workers.py` entry point, and registering the queue's database for migrations.

Three pieces cooperate:

- **Tasks.** A *task* is an ordinary function you decorated with `@app.queue.task()`. The decorator gives the function a second way to be called: instead of running now, it can be packed into a message and run later.
- **The queue.** `app.queue` is the Huey instance. It holds pending task messages until something picks them up. Where those messages actually live - memory, a SQLite file, Redis - is a config choice.
- **The worker.** In production, a separate process (the Huey *consumer*) watches the queue, pulls task messages off it, and runs them. Your web process enqueues; the worker executes. They are different processes, often on different machines.

The split between enqueuing and executing is the whole point, and it has one consequence worth stating early: the web process and the worker process don't share memory. A task's arguments are *serialized* - turned into bytes, sent through the queue, and rebuilt on the other side. So you pass a user's id, not the `User` object; the task looks the row up itself.

```
controller  ─enqueue─▶  app.queue  ─dequeue─▶  worker  ─runs─▶  your task
(web process)          (the queue)             (separate process)
```

### Immediate Mode

There's an exception to the "separate process" picture, and it's the one you'll spend most of your development time in.

When the queue is configured with `immediate: True` - the default in development and testing - calling a task runs it **synchronously, in the same process, right now**. No worker, no serialization round-trip, no waiting. The task behaves like a normal function call.

This means you can build and test task code without ever starting a worker. You flip to a real backend (and a real worker) for production, and the same task code runs queued instead of immediate. The mode is a config switch; your tasks don't change.

The generated app is already set up this way: immediate mode for `dev` and `test`, Redis for `prod`. [Configuration](#configuration) covers the switch in full.

---

## Setup

Unlike the storage or auth addons, the queue is **not** something you install - every generated app has it. The config lives in `config/storage.py` (alongside `DATABASES` and `CACHE` - that file holds your app's persistence infrastructure, not just file storage), and the `tasks/` directory already exists with one task in it.

So there's nothing to set up before you write your first task. What you do need to know is which backend you're running:

Backend | Stores messages in | Use for
------- | ------------------ | -------
`MemoryHuey` | process memory (immediate mode) | development, tests
`SqliteHuey` | a SQLite file | small single-server apps
`SqlHuey`    | a SQL database via Peewee | production without Redis
`RedisHuey`  | Redis | production, most apps
`PriorityRedisHuey` | Redis | Supports [task priorities](https://huey.readthedocs.io/en/latest/guide.html#priority){target=_blank}
`RedisExpireHuey`   | Redis | Stores the results in new Redis keys
`PriorityRedisExpireHuey` | Redis | Combines the behavior of `RedisExpireHuey` and `PriorityRedisHuey`.

The generated config uses `MemoryHuey` in immediate mode for `dev` and `test`, and `RedisHuey` for `prod`. You can leave that alone until you deploy. The full reference for each backend - connection options, per-environment switching - is in [Configuration](#configuration); you don't need it to follow the next several sections.

---

## Defining Tasks

Tasks live in the `tasks/` directory. Decorate a function with `@app.queue.task()` and it becomes a task:

```python
# tasks/__init__.py
from ..main import app


@app.queue.task()
def generate_report(report_id):
    from ..models import Report

    report = Report.get_by_id(report_id)
    report.build_pdf()
    report.notify_owner()
```

That's the whole declaration. `generate_report` is still a normal function - you can import it and call it - but it now also carries the machinery to be enqueued.

A freshly generated app ships one task already, in that same file:

```python
# tasks/__init__.py
from proper.emails import EmailMessageDict

from ..main import app


@app.queue.task()
def send_email_task(message: EmailMessageDict, via: str | None = None):
    mailer = app.mailers[via] if via else app.mailer
    mailer.send_now(message)
```

This is the task behind `email.send_later()` - the Emails guide's [Sending in the background](/docs/emails) section covers that side. The storage system uses the queue too: `attachment.purge_later()` and variant cleanup are both tasks. You'll see the pattern repeated because it's the right one: anything slow or failure-prone, push to a task.

### Arguments Must Be Serializable

The task's arguments travel through the queue as bytes, so they have to survive the trip: strings, numbers, booleans, `None`, and lists or dicts of those.

A model instance does not survive the trip. Pass the id instead, and re-fetch inside the task:

```python
# Wrong - the User object can't be serialized through the queue
send_welcome_email(user)

# Right - pass the id, look it up in the task
send_welcome_email(user.id)


@app.queue.task()
def send_welcome_email(user_id):
    from ..models import User

    user = User.get_by_id(user_id)
    # ...
```

There's a second reason to re-fetch beyond serialization: a queued task might run seconds or minutes after it was enqueued. Re-fetching gets you the *current* row, not a stale snapshot from when the request handler ran.

### Context Tasks

In the web process a controller concern opens a connection at the start of each request and closes it on teardown - but the worker process has no controllers and no request cycle, so nothing manages the connection there.

A **context task** wraps every run of a task in a context manager, so it can be used to give a task that same open-and-close discipline:

```python
# tasks/__init__.py
from ..main import app
from ..models import db


@app.queue.context_task(db)
def archive_old_orders(cutoff):
    # `db` is connected for the duration of this task, then closed
    Order.update(archived=True).where(Order.created_at < cutoff).execute()
```

:::warning
Wrap any task that touches the database this way once you run a real worker.
:::

### `task()` Decorator Options

The decorator takes several keyword arguments:

```python
@app.queue.task(retries=0, retry_delay=0, priority=None, context=False, name=None, expires=None)
def my_task(arg1, arg2):
    return result
```

| Parameter | Description |
| --------- | ----------- |
| `retries` | Number of automatic retries on failure. Default `0`. |
| `retry_delay` | Seconds to wait between retries. Default `0`. |
| `priority` | Default priority for this task, higher runs first (requires a priority-aware backend). Default `None`. |
| `context` | If `True`, the running `Task` object is passed to your function as a `task` keyword argument. |
| `name` | Custom task name. Defaults to `module.function`, which is what identifies the task across processes. |
| `expires` | Discard the task if it hasn't run within this window. An int (seconds), `timedelta`, or `datetime`. |

`retries` and `expires` are the two you'll reach for most; both come up again in [Retries and Error Handling](#retries-and-error-handling).

---

## Enqueuing Tasks

To enqueue a task, call it like a function:

```python
def create(self):
    self.form.save()
    generate_report(self.report.id)
    self.response.redirect_to("Report.show", self.report)
```

In immediate mode (the default for development) `generate_report` runs right there, before `redirect_to`. In production it's packed into a message, dropped on the queue, and a worker runs it later. Same line of code.

Calling a task always returns a `Result` handle - in both modes:

```python
res = generate_report(report.id)
```

In immediate mode the task has already finished by the time you hold `res`, so `res()` gives you its return value straight away. In queued mode the task hasn't run yet, and `res()` returns `None` until a worker finishes it. [Results](#results) covers the handle in detail. Plenty of tasks - the report generator above - have nothing to return and nothing to wait on, so you just ignore the handle.

If you are using the `PriorityRedisHuey` backend, you can also define a `priority` for a single call:

```python
generate_report(report.id, priority=50)
```

---

## Scheduling Tasks

To run a task *later* rather than as soon as a worker is free, use `.schedule()`:

```python
# Run roughly 60 seconds from now
generate_report.schedule(args=(report.id,), delay=60)

# Run at a specific time
from datetime import datetime, timedelta

eta = datetime.now() + timedelta(hours=1)
generate_report.schedule(args=(report.id,), eta=eta)

# Schedule
generate_report.schedule(args=(report.id,), delay=60)
```

`args` is a tuple of the task's positional arguments; `kwargs` is available too. `delay` is seconds from now; `eta` is an absolute `datetime`. Pass one or the other, not both.

A scheduled task sits in the queue's schedule until its time comes, then becomes a normal pending task. That last hop is the worker's *scheduler*, which is on by default (`periodic: True` in the consumer config) - so scheduling only does anything with a worker running, or in immediate mode where `delay` and `eta` are simply ignored and the task runs now.

:::note
In immediate mode there is no scheduler and no clock to wait on, so a scheduled task runs immediately. Don't lean on `delay` for correctness in tests - assert that the task *did its work*, not that time passed.
:::

---

## Periodic Tasks

For work that runs on a recurring schedule - nightly cleanup, hourly sync, a digest every Monday - use `@app.queue.periodic_task()` with a `crontab()` schedule:

```python
from huey import crontab

from ..main import app


@app.queue.periodic_task(crontab(minute="0", hour="*/2"))
def cleanup_expired_sessions():
    from ..models import Session

    Session.delete().where(Session.expires_at < datetime.now()).execute()
```

A periodic task takes **no arguments** - the scheduler enqueues it, and nothing is there to pass anything in - and its return value is discarded. It otherwise accepts the same options as `task()` (`retries`, and so on).

:::warning
Periodic tasks are driven by the worker's scheduler. No worker running means nothing fires so **in immediate mode they never fire on their own**; call the underlying function directly if you want to exercise it in a test.
:::

### `crontab()` Syntax

`crontab()` describes *when* a periodic task should run, with the five standard cron fields:

```python
crontab(minute="*", hour="*", day="*", month="*", day_of_week="*")
```

Each field accepts a few syntaxes:

| Syntax | Meaning |
| ------ | ------- |
| `*` | every value |
| `*/n` | every `n` intervals |
| `m-n` | the range `m` through `n`, inclusive |
| `m,n` | the specific values `m` and `n` |

`day_of_week` runs `0` (Sunday) through `6` (Saturday). The finest granularity is one minute.

```python
# every 10 min, 9am-5pm
crontab(minute="*/10", hour="9-17")

# daily at 3am
crontab(minute="0", hour="3")

# every half hour, on the hour and half-hour
crontab(minute="0,30")
```

---

## Results

When a task returns a value, you read it back through the `Result` handle the call gave you:

```python
res = generate_report(report.id)

# the return value, or None if not ready yet
res()

# block until the worker finishes, then return it
res(blocking=True)

# block up to 5s, then raise ResultTimeout
res(blocking=True, timeout=5)
```

Method or property | Description
------------------ | -----------
`res()` / `res.get(**kw)` | Fetch the result. Returns `None` if the task hasn't finished.
`res.id` | The task's unique id.
`res.revoke()` | Cancel the task, if it hasn't started running.
`res.restore()` | Un-cancel a revoked task.
`res.is_revoked()` | Whether the task is currently revoked.
`res.reschedule(eta=, delay=)` | Move the task to a new run time.
`res.reset()` | Clear the cached result so it can be re-read after a retry.

Two behaviors to keep in mind:

- **Results are read-once by default.** The first `res()` that returns a value also deletes it from the result store. Pass `res.get(preserve=True)` if you need to read it more than once.
- **Failures surface on read.** If the task raised an exception, calling `res()` re-raises it wrapped in a `TaskException` that carries the original error. The failure travels with the result; it doesn't disappear.

Most tasks don't have a meaningful return value and you never touch the handle. Reach for `Result` when one task's output feeds the next thing the request needs - and if you find yourself blocking a request handler on `res(blocking=True)`, ask whether that work belonged in a task at all.

:::note
The queue's result store also doubles as a small **key/value store** you can use directly - even if the backend is not Redis-based - for cross-process scratch data that doesn't justify a database table:

```python
app.queue.put("last-sync-cursor", cursor)
# peek=True leaves the value in place
app.queue.get("last-sync-cursor", peek=True)
```

Both are thin pass-throughs to Huey; its docs cover the corners.
:::

---

## Retries and Error Handling

A background task runs unattended. When it fails, there's no user looking at a stack trace - so you decide in advance what failure should do.

### Automatic Retries

The simplest policy is "try again a few times." Set `retries` and `retry_delay` on the decorator:

```python
@app.queue.task(retries=3, retry_delay=60)
def sync_to_crm(contact_id):
    from ..models import Contact

    contact = Contact.get_by_id(contact_id)
    crm_client.upsert(contact.to_payload())
```

If `sync_to_crm` raises, the worker re-enqueues it - up to three more times, waiting 60 seconds between attempts. If it still fails after the last retry, the exception is stored as the task's result and the task is done.

This is the right default for anything that talks to a network: third-party APIs, webhooks, remote storage. The failure is usually transient, and a delayed retry clears it.

### Forcing a Retry

To retry on a condition that *isn't* an exception - a rate-limit response, a "not ready yet" status - raise `RetryTask` yourself:

```python
from huey import RetryTask


@app.queue.task()
def fetch_feed(url):
    response = httpx.get(url)
    if response.status_code == 429:
        raise RetryTask(delay=60)   # rate-limited; come back in a minute
    return response.json()
```

`RetryTask` re-enqueues the task regardless of the `retries` setting - including when `retries=0`. The `delay` is optional.

### Canceling a Task

To stop a task from running again - or to control whether a *failure* should retry - raise `CancelExecution`:

```python
from huey import CancelExecution


@app.queue.task(retries=3)
def process_upload(upload_id):
    upload = Upload.get_or_none(Upload.id == upload_id)
    if upload is None:
        raise CancelExecution(retry=False)   # the row is gone; never retry
    if upload.is_corrupt():
        raise CancelExecution(retry=True)    # bad data; retry anyway
    upload.process()
```

`CancelExecution(retry=False)` kills the task outright. `CancelExecution(retry=True)` forces a retry even past the retry count. `CancelExecution()` with no argument retries only if retries remain. Use it when the task can tell, mid-run, that continuing is pointless.

### Expiring Stale Tasks

Some work is only worth doing promptly. A "your export is ready" notification that's been stuck in the queue for an hour is just noise. `expires` discards a task that waited too long:

```python
@app.queue.task(expires=60)   # must start within 60s of being enqueued
def notify_export_ready(user_id):
    ...

# Or per-call, overriding the decorator
notify_export_ready(user.id, expires=timedelta(minutes=5))
```

An expired task is dropped without running and without error. `expires` accepts an int (seconds), a `timedelta`, or an absolute `datetime`.

---

## Revoking Tasks

Retries and expiration are policies set before a task runs. *Revoking* is the after-the-fact version: you've already enqueued something and now you want to call it off.

```python
# Cancel one specific enqueued task, through its Result handle
res = generate_report(report.id)
res.revoke()

# Cancel every pending instance of a task, and later allow them again
generate_report.revoke()
generate_report.restore()

# Skip just the next run of a periodic task
cleanup_expired_sessions.revoke(revoke_once=True)

# Pause a periodic task until a point in time
from datetime import datetime, timedelta

cleanup_expired_sessions.revoke(revoke_until=datetime.now() + timedelta(hours=3))
```

Revoking only catches a task the worker hasn't started yet - it's a "don't run this," not a "kill it mid-run." A task already executing runs to completion.

---

## Coordinating Work: Locks, Pipelines, and Signals

Past the single-task lifecycle, Huey has three features for coordinating tasks. They come up less often, so this section is a brief tour - the [Huey documentation](https://huey.readthedocs.io/){target=_blank} is the full reference for each.

**Locks** keep two runs of the same task from overlapping - useful when a periodic task could be slow enough to still be running when the next tick fires:

```python
@app.queue.periodic_task(crontab(minute="*/5"))
@app.queue.lock_task("rebuild-search-index")
def rebuild_search_index():
    ...
```

If the lock is already held, the task is skipped (and raises `TaskLockedException`, which retries if the task is configured to). `lock_task` also works as a context manager around just part of a task.

**Pipelines** chain tasks so each receives the previous one's return value:

```python
pipeline = fetch.s(url).then(parse).then(store)
result_group = app.queue.enqueue(pipeline)
```

A returned `tuple` is spread as `*args` into the next task; a `dict` as `**kwargs`. `Task.map()` is the related tool for applying one task across many argument sets.

**Signals** are hooks that fire as tasks move through their lifecycle - enqueued, executing, complete, error, revoked. They're how you'd wire task failures into an error tracker:

```python
from huey.signals import SIGNAL_ERROR


@app.queue.signal(SIGNAL_ERROR)
def report_task_failure(signal, task, exc=None):
    error_tracker.capture(exc, task_name=task.name)
```

Huey also has `pre_execute` / `post_execute` hooks and an `on_startup` hook for per-worker setup (opening a shared connection, say). Reach for these when you have cross-cutting behavior that shouldn't be copied into every task body.

---

## Running Workers

Everything so far runs in immediate mode without a worker. Production is where the worker earns its keep: a separate, long-lived process that drains the queue.

The generated app ships the entry point at the project root, `workers.py`:

```python
# workers.py
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

Run it from the project root:

```bash
$ python workers.py
```

It imports your app (which loads the queue config), builds a Huey `Consumer`, and runs it until you stop it. The consumer does three jobs at once: it runs pending tasks, it moves scheduled tasks onto the queue when their time comes, and - if `periodic` is on - it fires periodic tasks. Leave it running and your queued, scheduled, and periodic tasks all start working.

In development you rarely need it: immediate mode handles everything in-process. Start `workers.py` when you specifically want to exercise the queued path - debugging a serialization issue, checking a `crontab()` schedule.

### Running in Production

In production the worker is a process you have to keep alive, restart on crash, and start on boot - the same problem as your web server. A process manager handles it. Here's a systemd unit:

```ini
# /etc/systemd/system/myapp-worker.service
[Unit]
Description=myapp background worker
After=network.target redis.service

[Service]
Type=simple
User=myapp
WorkingDirectory=/srv/myapp
Environment=APP_ENV=prod
ExecStart=/srv/myapp/.venv/bin/python workers.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
$ sudo systemctl enable --now myapp-worker
$ sudo systemctl status myapp-worker
$ journalctl -u myapp-worker -f          # follow the worker's logs
```

Two settings matter here. `WorkingDirectory` must be the project root so `import myapp` and the relative paths in your config resolve. `Environment=APP_ENV=prod` is what flips the config off immediate mode and onto your real backend - without it the worker boots in immediate mode and the queue does nothing.

Supervisor, Docker, or a platform's process model (a `worker:` entry in a Procfile, a second container in a compose file) all work the same way: one long-lived process running `python workers.py` with `APP_ENV=prod` set.

### Scaling Out

When one worker can't keep up, there are two dials:

- **More threads in one process.** Raise `workers` in `QUEUE_CONSUMER` ([Consumer Settings](#consumer-settings)). One process, several tasks at once. Simple, and enough for most apps.
- **More worker processes.** Run `workers.py` more than once - several systemd units, several containers. They all pull from the same queue, so the work spreads across them. This is how you scale across machines.

The web process and the worker process must point at the **same queue backend** - the same Redis, the same SQL database. That's the channel they talk over. `MemoryHuey` can't be that channel: its messages live in one process's memory, so a separate worker would be watching an empty queue. Any setup with a real worker needs `SqliteHuey`, `RedisHuey`, or `SqlHuey`.

:::tip
Run exactly **one** consumer with `periodic: True`. If several worker processes all have the periodic scheduler on, every periodic task fires once per process. Keep `periodic: True` on one unit and set it to `False` on the rest, or run a single dedicated scheduler process.
:::

---

## Configuration

The queue is configured by two dictionaries in `config/storage.py`: `QUEUE` (the backend) and `QUEUE_CONSUMER` (the worker process).

### Queue Backend (`QUEUE`)

The `type` key is the Huey backend class to use. Every other key is passed straight to that backend's constructor.

**MemoryHuey** - the development and test default:

```python
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}
```

`immediate: True` is what makes tasks run synchronously in-process. `immediate_use_memory: True` keeps results in memory too, so you never touch a real store while developing. No worker needed.

**SqliteHuey** - a single file, no server to run:

```python
QUEUE = {
    "type": "huey.SqliteHuey",
    "database": "storage/queue.sqlite3",
}
```

Good for small single-server deployments. A real worker process can read this file, so `workers.py` works. (Proper renames `database` to Huey's `filename` argument for you - write `database`.)

**RedisHuey** - the production default:

```python
QUEUE = {
    "type": "huey.RedisHuey",
    "name": "myapp",
}
```

Fast, battle-tested, and the natural fit when you're already running Redis for caching or sessions. Requires the `redis` package - `uv add redis`.

**SqlHuey** - a SQL database, via Peewee:

```python
QUEUE = {
    "type": "huey.contrib.sql_huey.SqlHuey",
    "dbtype": "peewee.SqliteDatabase",
    "database": "storage/queue.sqlite3",
}
```

Use this when you want a real worker but would rather not add Redis to your stack - the queue rides on a database you already operate. `dbtype` is the Peewee database class; the rest (`database`, `host`, `port`, `user`, `password`) are its connection parameters. Proper registers the resulting database as `app.db["proper_queue"]` so it can be migrated - see [Database Migrations for SQL Backends](#database-migrations-for-sql-backends).

### Consumer Settings (`QUEUE_CONSUMER`)
{id="consumer-settings"}

These configure the worker process - `workers.py` reads them and passes them to the Huey `Consumer`. Every key has a sensible default; override only what you need.

```python
QUEUE_CONSUMER = {
    "workers": 1,                  # worker threads/processes in this consumer
    "periodic": True,              # run the periodic-task scheduler
    "initial_delay": 0.1,          # queue polling interval, seconds
    "backoff": 1.15,               # back-off factor while the queue is empty
    "max_delay": 10.0,             # longest interval between polls, seconds
    "scheduler_interval": 1,       # scheduler check interval, 1-60 seconds
    "worker_type": "thread",       # "thread", "process", or "greenlet"
    "check_worker_health": True,   # monitor and restart dead workers
    "health_check_interval": 10,   # health check frequency, seconds
    "flush_locks": False,          # clear stale task locks on startup
    "extra_locks": "",             # comma-separated extra lock names to register
}
```

`workers` and `periodic` are the two you'll touch - see [Scaling Out](#scaling-out). `worker_type` is worth knowing: `"thread"` is the default and fine for I/O-bound tasks (most of them - network calls, database work); switch to `"process"` for CPU-bound tasks that would otherwise fight over the GIL.

### Per-Environment Configuration

The generated `config/storage.py` switches backends by environment, keyed off `APP_ENV`:

```python
env = os.getenv("APP_ENV", "dev")

# Development (default) - immediate mode, no worker
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
}

if env == "test":
    QUEUE = {
        "type": "huey.MemoryHuey",
        "immediate": True,
        "immediate_use_memory": True,
    }

if env == "prod":
    QUEUE = {
        "type": "huey.RedisHuey",
        "name": "myapp",
    }
```

This is why the same task code runs synchronously on your laptop and queued in production: nothing in the task changed, only which `QUEUE` dict was active when the app booted. Setting `APP_ENV=prod` (as the [systemd unit](#running-in-production) does) is what selects the production backend.

---

## Database Migrations for SQL Backends

`SqliteHuey` and `RedisHuey` manage their own storage - there's nothing to migrate. `SqlHuey` is different: it keeps tasks in a SQL database, and that database needs its schema created and kept up to date like any other.

Proper registers the `SqlHuey` database as `"proper_queue"` in `app.db`, so the standard `proper db` commands work against it with the `--db` flag:

```bash
$ proper db create "description" --db=proper_queue
$ proper db migrate --db=proper_queue
$ proper db rollback --db=proper_queue
```

The migration files live in `db/proper_queue/`. The backend uses three tables - `kv` (key/value storage), `schedule` (scheduled tasks), and `task` (pending task data). You don't write these migrations by hand; `proper db create` generates them from the backend's models. You just need to run `migrate` on the queue database the same way you run it on `main`.

---

## Testing

Tests run in immediate mode (the generated `test` config sets `immediate: True`), and that shapes how you test task code: **calling a task in a test runs it, synchronously, right there**. There's no worker to start and no queue to drain.

So a controller test that enqueues a task already exercises the task:

```python
def test_create_report_builds_pdf(client, user):
    client.login(user)
    response = client.post("/reports", data={"title": "Q3"})

    report = Report.get(Report.title == "Q3")
    assert report.pdf is not None   # generate_report ran during the POST
```

The task ran inline during the request - by the time `client.post` returns, `generate_report` is done and its effects are on the row.

That covers most cases. Two things immediate mode does *not* do, because there's no scheduler and no clock:

- **`schedule(delay=...)` runs now.** `delay` and `eta` are ignored. Test that the task did its work, not that time advanced.
- **Periodic tasks don't fire.** Nothing ticks. To test the body of a periodic task, call the underlying function directly:

  ```python
  def test_cleanup_removes_expired_sessions(db):
      Session.create(expires_at=datetime(2020, 1, 1))
      cleanup_expired_sessions.call_local()   # run the function body directly
      assert Session.select().count() == 0
  ```

To test the *queued* path itself - serialization, the worker, a real backend - you'd point a test at `SqliteHuey` and run a consumer, but that's an integration test you run deliberately, outside the normal unit-test loop. For the everyday "did my task do the right thing" question, immediate mode is the answer.

---

## What's Next

Background tasks touch email, storage, and deployment. A few places to go from here:

- [Sending Emails](/docs/emails) - `email.send_later()` is built on the `send_email_task` task; that guide covers composing and sending mail.
- [File Storage](/docs/storage) - `attachment.purge_later()` and variant cleanup are tasks; the storage guide shows the eager-loading patterns that schedule variant generation.
- [Deployment and Performance](/docs/deployment) - running the worker alongside your web server, and sizing both for real traffic.
- [Huey documentation](https://huey.readthedocs.io/){target=_blank} - the full reference for everything `app.queue` exposes: pipelines, signals, locks, serializers, and the consumer internals.
