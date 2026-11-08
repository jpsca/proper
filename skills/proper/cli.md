---
title: CLI, Serving and Logging
description: The `proper` command (run, check, routes, generators, db), what `proper run` starts, `proper check`'s checks, and the `proper` logger
last_verified: 2026-11-07
sources:
  - src/proper/cli
  - src/proper/check
  - src/proper/helpers/logs.py
  - src/proper/helpers/server.py
---

# CLI, Serving and Logging

How to run, check and observe a Proper app from the command line. Generator syntax is in [generators.md](generators.md); migrations commands in [migrations.md](migrations.md).

## Table of Contents

- [CLI](#cli)
- [Checking](#checking)
- [Serving](#serving)
- [Logging](#logging)


## CLI

The `proper` command provides these subcommands:

```bash
proper run                          # Start the server (Bearings, port 2300)
proper run --host=0.0.0.0 --port=N --workers=N  # Defaults: config PORT and WORKERS
proper routes                       # Display all registered routes
proper check                        # Find the mistakes of the app; exits with 1 on an error

proper g resource Photo title:str   # Generate model + controller + form + views
proper g model Photo title:str      # Generate model only
proper g controller Photos          # Generate a controller
proper g email Welcome              # Generate an email class and its views
proper g seed photos                # Generate a seed file
proper g channel Chat               # Generate a channel (channels addon)

proper db create "description"      # Create a migration from model changes
proper db migrate                   # Run all pending migrations (--fake marks them done)
proper db prepare                   # Migrate every database, then seed main
proper db migrate_to TARGET         # Run migrations up to TARGET
proper db rollback                  # Rollback the latest migration
proper db merge "name"              # Merge migrations into one
proper db todo                      # Show pending migrations
proper db done                      # Show applied migrations
proper db seed [name]               # Run the seeds (one, by name, or all)

proper install auth                 # Install authentication system
proper install i18n                 # Install internationalization
proper install storage              # Install file storage
proper install channels             # Install channels addon
proper install rich_text            # Install the rich text editor

proper jx info                      # Folders, autoescape, tags and views of the catalog (--format=json)
proper jx compile                   # Compile every view now; fails listing the ones that don't compile
```

All commands accept a `--help` parameter that shows more details.

Most `db` commands accept `--db=NAME` to target a specific database (default: `main`; `migrate` and `prepare` default to every database).


## Checking

`proper check` imports the app and runs the checks of `proper.check.CHECKS` (each is `check_x(app) -> list[Problem]`; `run_checks(app)` runs them all). It prints one problem per line, `path:line[:col]: error|warning: message`, then `N error(s), M warning(s)` (or `No problems found.`), and exits with 1 when there is an error. Run it from the project root: migrations and seeds are read from `db/` relative to the current folder.

| Check | Level | What |
|---|---|---|
| `check_gil` | error/warning | The GIL is on (`sys._is_gil_enabled()`): error unless `ALLOW_GIL` (then a warning). On a free-threaded build it imports the app's package again in a new process, with `-W always::RuntimeWarning` and without `PYTHON_GIL`, and names the extension modules Python warns about. |
| `check_config` | warning | An unknown setting close to a known one (a typo). Settings of the app's own, unlike any known one, are not reported. |
| `check_services` | error | `STORAGE` not in `STORAGES`; a storage `type` that is not a `Service` subclass (at any depth); a `MAILERS` `type` that doesn't import. |
| `check_controllers` | error | A route, or an error handler, whose controller can't be loaded (a class must be at the top of its module); a `before`/`after` `do` that is not a method. |
| `check_action_names` | warning/error | Warning: a name in `only`/`exclude` of a `before`/`after` callback or of `rate_limit`, or in `skip_authentication`, that is not a routed action. A list declared by a base class or concern is checked against the actions of every routed controller based on it. Error: a method name in `rate_limit` (`to`, `within`, `by`, `react_with`) that the controller doesn't have. Only classes of the app. |
| `check_routes` | error | A route with the method, path and host of an earlier one (it never matches); a route name used for routes with different paths (`url_for` builds the first). |
| `check_views` | error/warning | Error: a view that doesn't compile (`compile_views(app, force=True)`, so it writes the compiled views). Warning: there is no views compiler for this platform, so they were not checked. |
| `check_view_urls` | error | A `url_for('Name', ...)` with a literal name in a view (read from the compiled modules): no such route (with a "did you mean"), or a placeholder of its path not given. A call with an object or `**kwargs` is checked only for the name. Compiled modules of deleted templates are skipped. |
| `check_code_urls` | error | The same for `url_for(...)`/`redirect_to(...)` (as a function or a method) in the app's Python files, parsed with `ast` in threads. Names starting with `/` or `http` are paths. |
| `check_models` | error | A field that hides a method (not a property) of a base class; two models of a database with the same table; a foreign key to a model that `models/__init__.py` doesn't import, or of another database; a `DeferredForeignKey` never resolved. |
| `check_migrations` | error/warning | Error: the models of a database are not what its migrations make (replayed with `fake=True`, no database needed); a migration that can't be read (the models of that database are then not compared). Warning: a `.py` in `db/<db>/` that is not named `NNN_name.py`; two migrations with the same number. |
| `check_seeds` | error/warning | Warning: a seed without `envs`, or with `envs` as a string; a `.py` in the seeds folder that `__init__.py` doesn't import. Error: a seed without `seed()`; seeds that don't import. |
| `check_forms` | error | A field of a form with `Meta.orm_cls` that is not an attribute of the model (`save()` would drop its value). |
| `check_emails` | error | An `EmailMessage` subclass without `body` and without `views/emails/<name>.jx` or `.txt.jx`. A class named `Base...`, or with subclasses, is skipped as a base. |
| `check_locales` | warning | A locale that lacks keys another has. |

Only the classes defined in the app's package are checked.


## Serving

`proper run` starts Bearings with the app. It refuses to start on a Python with the GIL: install a free-threaded one with `uv python install 3.14t` (the blueprint pins it in `.python-version` and its Dockerfile installs it), or set `ALLOW_GIL = True` to serve with the GIL anyway, at the cost of memory and parallelism. On a free-threaded Python, an extension module that has not declared itself safe turns the GIL back on when imported; Python names it in a `RuntimeWarning`, and `proper run` stops with the same error.

What it starts, from the config:

- `WORKERS` Bearings event loops per process, which never run Python; the app runs on one pool of `MAX_THREADS` threads.
- With a cable that serves WebSockets (`Cable`), that server, in the first web process, on `CABLE_PORT`.
- `PROCESSES` copies of the web server, all on the same port. One is right for most machines; with four or more cores a second one adds throughput for another copy of the app in memory.
- With `RELOAD` (which follows `DEBUG` when unset), the whole group restarts when a file under the app changes. The watcher is Proper's own (`proper.cli.reloader`, Linux inotify through `ctypes`); it skips `.git`, `.venv`, `node_modules`, `__pycache__`, compiled Python and editor temporary files. A server that dies on start is restarted by the next change, not by itself. On WSL it polls the modification times every second instead (inotify misses writes from Windows on `/mnt/c`); `PROPER_RELOAD_POLLING=1`/`0` forces polling or inotify.

There is no middleware parameter: Proper is not an ASGI application. Cross-cutting behavior goes in controller `before`/`after` callbacks and concerns, and TLS or compression belong to the reverse proxy in front of the app.


## Logging

The `proper` logger outputs debug information for:

- Each pipeline step: `[pipeline] GET /path -> step_name`
- Controller callbacks: `[ControllerName.action] before: callback_name`
- Callback halts: `[ControllerName.action] halted by before callback: callback_name`
- Template inference: `[ControllerName.action] rendering inferred template: photos/index.jx`
- Errors: `❌ ErrorType: message` (the request is on the access line with the same `request_id`)

All but the errors (written at the `error` level, so shown by default) need `LOG_LEVEL = "debug"`.

`proper.helpers.logger` is a `structlog.stdlib.BoundLogger` over the stdlib `proper` logger, at the level of `LOG_LEVEL`. Set the level with `LOG_LEVEL`: each controller action reads it once, the first time it runs. It takes `%s` arguments (formatted by the stdlib, only if the level lets the record through) and keyword arguments, which become fields of the line. An event under the level is dropped before it is built.

It is the recommended way for app code to log. Write the event as a fixed message and the data as keyword arguments; don't pass the `request_id`, Proper adds it:

```python
from proper.helpers import logger

logger.info("Order paid", order_id=order.id, amount=order.total)
logger.exception("Payment failed", order_id=order.id)  # in an `except` block
```

To add a field to every line until the end of the request (every logger's lines): `structlog.contextvars.bind_contextvars(user_id=current.user.id)`. Each request runs in its own context, so the field doesn't leak to the next one. Tasks enqueued during a request run with its `request_id` bound. Stdlib loggers also work; their fields go in `extra={...}`.

`proper run` has Bearings write one access line per request on stdout, outside `logging`, dropping the lines below `LOG_LEVEL` (Bearings' `access_log_level`); a line's level is its status's: `"error"` for a 4xx or a 5xx, `"info"` otherwise. The format is `LOG_FORMAT`'s (`_access_log` in `proper.cli.app_cli`), with structlog's keys (`timestamp`, `level`, `logger` = `"bearings"`, `event` = `"GET /path"`, `request_id` from the response's `X-Request-ID`, `method`, `path`, `query` if any, `status`, `size`, `duration` in seconds, `client`): `"json"`, one object per line; `"console"`, a short line, `19:53:02.464472Z [info]  200 GET /projects?page=2  (0.412ms; 3.12 KB)` (time of day, `[level]` padded to `[error]`'s width, status, method, path and query, duration, body size with 1 KB = 1024 bytes; the level in color when stdout is a terminal; no other fields); `"off"`, no access lines.

Creating the `App` calls `setup_logging(config.LOG_FORMAT)` (`proper.helpers.logs`; with `"console"`, the short line of the access log, `19:53:02.464472Z [info]  Order paid  order_id=42`: time of day, `[level]` padded to `[error]`'s width and in color in a terminal, event, then the other fields as `key=value`, without `request_id` and without `logger` when it is `proper`): one handler on the root logger, writing to `sys.stderr`, with structlog's `ProcessorFormatter`. Every logger goes through it (the app's, peewee's, huey's), and each line gets `timestamp` (ISO, UTC), `level`, `logger`, the record's extra fields, and the variables bound with `structlog.contextvars`. Each request runs in a context of its own with `request_id` bound (the same as `request.request_id` and the response's `X-Request-ID`), so every line written while answering it has it. `LOG_FORMAT = "off"` removes the handler; don't add another handler to the root logger (or call `logging.basicConfig()`) while it's on, or each line is written twice. To see the SQL: `logging.getLogger("peewee").setLevel(logging.DEBUG)`.
