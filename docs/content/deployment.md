---
title: Deployment and Performance
description: |
  How to run a Proper application in production. Covers free-threaded Python, the `proper run` server and its settings, sizing workers, threads and processes, production configuration, the Docker image, Compose and nginx, the background worker, a deploy checklist, and how Proper performs against other frameworks.
number_headers: true
---

# Deployment and Performance

In development, `proper run` starts a server, reloads it when you save a file, and nothing else needs thinking about. In production the questions change: which Python runs the app, how many requests it works on at once, how many database connections that opens, what sits in front of it, and where the background tasks run. Get these wrong and the app either wastes the machine or falls over under load.

Proper answers most of them with defaults and with the files a new app already has: a `Dockerfile`, a `compose.yml`, an nginx config, and an `.env.example` with the variables the production config reads. This guide explains what those files do and what each setting changes, so you can adjust them with a reason.

After reading this guide, you will know:

- Why Proper serves on free-threaded Python, and what happens when it isn't.
- What `proper run` starts, and what `INTERFACE`, `WORKERS`, `MAX_THREADS` and `PROCESSES` control.
- How to size those settings for your machine.
- Which environment variables and settings matter in production.
- How the Docker image is built, and how one image runs the web server, the worker and the migrations.
- How to put nginx in front of the app, including the WebSocket port.
- What to do, in order, on each deploy.
- How Proper performs compared to other Python, Ruby, Go and Rust frameworks.

---

## Free-threaded Python

Proper serves on free-threaded Python, the "t" builds of CPython: `3.14t` today. On those builds there is no GIL, so the threads of one process run Python code in parallel. That lets Proper run its server workers as threads that share one interpreter and one copy of the app, instead of one process per worker with a copy of everything in each.

The trade-off is measured: free-threaded Python is 5 to 10% slower per thread than the GIL build, and it uses much less memory for the same number of concurrent requests. Python 3.15 keeps free-threading as a separate build too, so this is not a temporary arrangement.

Install it with uv:

```bash
uv python install 3.14t
```

A new app is already set up for it. The blueprint pins the interpreter in `.python-version` and allows any 3.x from 3.14 in `pyproject.toml`:

```text {title=".python-version"}
3.14t
```

```toml {title="pyproject.toml"}
requires-python = ">=3.14,<4"
```

### When the GIL is on

`proper run` checks the interpreter before it starts. On a Python with the GIL it refuses:

```text
[ERROR] This Python has the GIL. Proper serves on free-threaded Python: install one with `uv python install 3.14t` and run the app with it.
To serve with the GIL anyway, set ALLOW_GIL = True in the config.
```

A free-threaded Python can also turn the GIL back on by itself: when it imports an extension module that has not declared itself safe without the GIL, it re-enables it and names the module in a `RuntimeWarning`. `proper run` notices and stops with a message pointing at that warning. The fix is to upgrade or replace that module.

If you can't, set `ALLOW_GIL = True` in the config. `proper run` then serves with the GIL and prints a warning at startup. The app works, but the threads no longer run in parallel, so you lose throughput, and you will need more processes (and more memory) to get it back.

---

## The server

`proper run` starts [Granian](https://github.com/emmett-framework/granian){target=_blank}, a server written in Rust, with your app:

```bash
proper run [--host 0.0.0.0] [--port PORT] [--workers N]
```

`--host` defaults to `0.0.0.0`; `--port` and `--workers` default to the `PORT` and `WORKERS` settings. Everything else comes from the config.

`PORT` is the port the server binds to: 2300 in the blueprint, read from the `PORT` environment variable. Don't confuse it with `HOST`, which is the public base URL of the app (`"YOUR-DOMAIN.com"` in production) and is only used to build absolute URLs.

### Interfaces: WSGI and RSGI

`INTERFACE` picks how Granian talks to the app.

Interface | How it runs a request | WebSockets
--------- | --------------------- | ----------
`"wsgi"` (default) | On one of Granian's own threads. No event loop, no hand-off. | No
`"rsgi"` | An async entry point hands the request to a thread pool that runs the sync pipeline. | Yes, in the same process

Proper controllers are sync, so WSGI is the fastest way to serve them: the thread that received the request runs it to the end. RSGI costs one thread hop per request, and in exchange serves WebSockets from the same process. Keep the default unless you have a reason; with WSGI, WebSockets are served by a separate process, described below.

### Workers, threads and processes

Three settings decide how much work the server does at once.

- **`WORKERS`** is the number of Granian workers in each process. On free-threaded Python they are threads, each with its own event loop, sharing the process and its memory.
- **`MAX_THREADS`** is how many threads run your code in each process. Each request holds one thread from start to finish, so this is how many requests the app works on at once. Under WSGI it is split between the workers of the process (rounded up, at least one per worker). `0` means `min(32, cpu_count + 4)`.
- **`PROCESSES`** is the number of copies of the web server `proper run` starts, all on the same port (the operating system spreads connections between them with `SO_REUSEPORT`).

`MAX_THREADS` has a second meaning worth keeping in mind: each thread opens its own database connection, so it is also how many connections a process can hold. Granian's own default for these threads is in the hundreds, which would flood the database with connections and buy nothing for Python code that uses the CPU, so Proper sets it explicitly.

Why more than one process, if threads already run in parallel? Threads of one interpreter still contend for the objects they share. On a machine with four or more cores, two smaller groups of threads do better than one big one: a second process adds about 10% throughput at 16 threads on a 10-core desktop. The price is a second copy of the app in memory.

### The cable process

WSGI has no WebSockets. When the app uses [channels](/docs/channels), `proper run` starts a second process that serves them over RSGI on `CABLE_PORT`. The channels addon sets `CABLE_PORT` to `PORT + 1` (2301), from the `CABLE_PORT` environment variable if set. With `CABLE_PORT = 0`, the default, no cable process starts. With `INTERFACE = "rsgi"` there is no cable process either, since the web server handles WebSockets itself.

In production, the reverse proxy routes `CABLE_PATH` (default `/cable`) to that port, with the WebSocket upgrade headers; the [nginx config](#the-reverse-proxy) below has that block. In development there is no proxy: when `DEBUG` is on, `render_importmap()` adds a `<meta name="cable-port">` tag to the page, and `cable.js` connects to that port on the same hostname.

Broadcasts made in the web process are forwarded to the cable process as a signed `POST` to `CABLE_PATH`. If the cable process is down, the message is lost and a warning is logged. For more than one machine, use `RedisCable`. The [Channels guide](/docs/channels) covers both.

### Reloading and stopping

`RELOAD` restarts the server when a file under the app changes. The default, `None`, follows `DEBUG`: on in development, off in production. The restart is done by a supervisor outside the server and covers the whole group - every web process and the cable process - not only Granian's workers.

Ctrl+C, or a `SIGTERM` to `proper run`, shuts down every process it started.

---

## Sizing

These are starting points, not rules. Measure with your own pages before changing them.

- Start with `WORKERS=1` and `PROCESSES=1`. That is right for a small server.
- On four or more cores, try `WORKERS=4`.
- If you have memory to spare, add `PROCESSES=2`, and check that your pages get faster.
- Keep `MAX_THREADS` at its default unless the number of database connections is what limits you. Remember that each thread is a connection, and with several processes, each process has its own `MAX_THREADS`.
- SQLite allows one writer at a time. More threads help reads, not writes.

Setting | Default | Blueprint reads it from | What it controls
------- | ------- | ----------------------- | ----------------
`PORT` | `2300` | `PORT` | The port the server binds to
`INTERFACE` | `"wsgi"` | - | `"wsgi"` or `"rsgi"`
`WORKERS` | `1` | `WORKERS` | Granian workers (threads) per process
`MAX_THREADS` | `0` (`min(32, cpus + 4)`) | - | Threads running your code per process; also database connections
`PROCESSES` | `1` | `PROCESSES` | Copies of the web server on the same port
`CABLE_PORT` | `0` (none) | `CABLE_PORT` (channels addon) | Port of the WebSocket process
`CABLE_PATH` | `"/cable"` | - | URL path the proxy routes to the cable process
`RELOAD` | `None` (follows `DEBUG`) | - | Restart on code changes
`ALLOW_GIL` | `False` | - | Serve on a Python with the GIL

---

## Production configuration

The blueprint's config files read `APP_ENV` and switch branches on it: `dev` by default, `test` for the test suite, and `prod` in production. The Docker image sets `APP_ENV=prod`. In the `prod` branches, `DEBUG` is off, `PROTOCOL` is `"https"`, the database is Postgres, the queue is Redis, and the mailer is SMTP.

Before your first deploy, edit `HOST` in `config/main.py` to your domain:

```python {title="config/main.py"}
if env == "prod":
    PROTOCOL = "https"
    HOST = "YOUR-DOMAIN.com"
```

### Environment variables

The `prod` branches read their secrets and connection settings from the environment. `.env.example` lists all of them; copy it to `.env` and fill it in.

Variable | What it is
-------- | ----------
`SECRET_KEYS` | Comma-separated secret keys, oldest to newest, each 48+ random characters
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | The Postgres database
`REDIS_HOST`, `REDIS_PORT`, `REDIS_NAME` | Redis, for the task queue
`SMTP_USERNAME`, `SMTP_PASSWORD` | The SMTP mailer
`WEB_PORT` | Host port Compose publishes the web server on (the container always listens on 2300)
`WORKERS`, `PROCESSES` | See [Sizing](#sizing)

New values are signed with the newest key, the last in the list, and every key in `SECRET_KEYS` is accepted when reading, so you can rotate them: append a new key, and once everything signed with the oldest has expired, remove it. Never deploy with an empty `SECRET_KEYS`.

### Databases

The default database class is `peewee.SqliteDatabase`, which is fine for a single server with modest write traffic. The blueprint's `prod` branch in `config/storage.py` switches to Postgres through a connection pool:

```python {title="config/storage.py"}
if env == "prod":
    DATABASES["main"] = {
        "type": "playhouse.postgres_ext.PooledPsycopg3Database",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
```

psycopg needs the `libpq5` system library, which the Docker image installs. If you keep SQLite in production, put the database file under `storage/` so it lives on a volume.

### Letting the proxy send files

`STATIC_X_SENDFILE_HEADER` hands file responses to the proxy: the app returns a header naming the file and nginx sends it, so a large download doesn't hold one of your threads. The blueprint sets it to `"X-Accel-Redirect"`, the nginx header, in production; Apache and lighttpd use `"X-Sendfile"`. See [Assets](/docs/assets) and [Storage](/docs/storage).

---

## Docker

The blueprint's `Dockerfile` builds a two-stage image on `debian:bookworm-slim`. The official `python` Docker images have no free-threaded variant, so uv installs the interpreter itself. A trimmed version:

```dockerfile {title="Dockerfile"}
ARG PYTHON_VERSION=3.14t
ARG UV_VERSION=0.11.7
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- Stage 1: builder
FROM debian:bookworm-slim AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_PYTHON=3.14t
RUN uv python install 3.14t

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev
COPY . .
RUN uv sync --frozen --no-dev

# --- Stage 2: runtime
FROM debian:bookworm-slim AS runtime
COPY --from=builder /python /python
ENV APP_ENV=prod PORT=2300 \
    VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libpq5 libvips \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN mkdir -p storage log && chown -R app:app storage log
USER app

EXPOSE 2300 2301
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/up' % os.environ.get('PORT','2300'), timeout=2)" || exit 1
CMD ["proper", "run"]
```

What each part does:

- **The builder** installs `3.14t` into `/python`, then installs the dependencies in their own layer, so Docker reuses that layer until `pyproject.toml` or `uv.lock` change. Only then does it copy your code and install the project.
- **The runtime stage** copies the interpreter and `/app` (code and virtualenv) from the builder. `/python` is the same path in both stages, so the virtualenv's links to the interpreter keep working. It adds `libpq5` for Postgres and `libvips` for image processing; the full file has commented lines for `poppler-utils` and `ffmpeg` if you preview PDFs or videos.
- **The app runs as `app`**, an unprivileged user. `storage/` and `log/` are its writable directories; mount volumes there.
- **The health check** requests the app's `/up` route, which every new app has.

Build it with:

```bash
docker build -t myapp:latest .
```

### One image, three commands

The same image runs everything. Only the command changes:

```bash
docker run ... myapp:latest                     # web server: proper run
docker run ... myapp:latest python workers.py   # background worker
docker run --rm ... myapp:latest proper db migrate
```

Running the worker from the same image as the web server matters: both import exactly the same tasks and models, so a task enqueued by one version is never run by another. The blueprint also has a `Dockerfile.workers`, which builds on the app image and only changes the command and disables the HTTP health check, for when you need to push a separate worker image to a registry.

---

## Compose and the reverse proxy

### Compose

`compose.yml` runs the app with Postgres and Redis managed elsewhere, reached through the variables in `.env`:

```yaml {title="compose.yml"}
x-app: &app
  image: myapp:latest
  build:
    context: .
    dockerfile: Dockerfile
  env_file:
    - .env
  environment:
    APP_ENV: prod
  restart: unless-stopped

services:
  web:
    <<: *app
    ports:
      - "${WEB_PORT:-2300}:2300"
      - "${CABLE_PORT:-2301}:2301"
    volumes:
      - storage:/app/storage

  worker:
    <<: *app
    command: ["python", "workers.py"]
    healthcheck:
      disable: true
    volumes:
      - storage:/app/storage

  migrate:
    <<: *app
    command: ["proper", "db", "prepare"]
    restart: "no"
    profiles: ["tools"]

volumes:
  storage:
```

- **`web`** publishes the web server and the cable port, and mounts the `storage` volume for uploads and the cache file.
- **`worker`** is the same image running `python workers.py`, with the health check turned off because it serves no HTTP.
- **`migrate`** is a one-off job behind the `tools` profile, so `docker compose up` never starts it. It runs `proper db prepare`, which runs `proper db migrate` and then `proper db seed`.

The order is:

```bash
cp .env.example .env              # then fill in the secrets and hosts
docker compose build
docker compose run --rm migrate   # apply migrations once
docker compose up -d web worker
```

### The reverse proxy

The app should not face the internet directly. Put nginx (or another proxy) in front of it to terminate TLS, serve the static assets from disk, and route the WebSockets. The blueprint's `deploy/nginx.conf` has the whole server block, with the TLS lines commented out. Its locations:

```nginx {title="deploy/nginx.conf"}
# Fingerprinted assets: strip the hash and serve the file from disk
location ~* "^\/assets\/(.*)-[a-z0-9]{12,}\.([a-z0-9]+)$" {
  rewrite "^\/assets\/(.*)-[a-f0-9]{12,}\.([a-z0-9]+)$" /assets/$1.$2 break;
  try_files $uri =404;
}

location /assets/ {
  alias /var/www/myapp/myapp/assets;
}

# WebSockets: the cable process
location /cable {
  proxy_pass http://127.0.0.1:2301;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_read_timeout 1h;
}

# Everything else: the web server
location / {
  proxy_pass http://127.0.0.1:2300;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
}

error_page 500 502 503 504 /500.html;
location = /500.html {
  root /var/www/myapp/myapp/assets;
}
```

The `/cable` block needs `proxy_http_version 1.1` and the `Upgrade` and `Connection` headers to pass the WebSocket handshake through, and a long `proxy_read_timeout` so nginx doesn't close idle connections. Remove the block if the app has no channels. If you change `CABLE_PATH`, change the location to match.

The `500.html` page is served by nginx, so visitors see it even when the app is down.

---

## Background workers

Tasks are run by the Huey consumer, a separate process started with `python workers.py` from the same image. It reads its options from `QUEUE_CONSUMER` in `config/storage.py`. The ones that matter for deployment:

Option | Blueprint value | What it is
------ | --------------- | ----------
`workers` | `1` (`4` in `prod`) | How many tasks run at once
`worker_type` | `"thread"` | `"thread"`, `"process"` or `"greenlet"`
`graceful_signal` | `"TERM"` | The signal that stops the consumer after the running tasks finish
`shutdown_timeout` | `None` | Seconds to wait for running tasks on a graceful stop; `None` waits

`graceful_signal` is `"TERM"` because `docker stop` and most supervisors send `SIGTERM`. With it, a deploy lets the running tasks finish instead of killing them halfway.

Whether you need the worker at all depends on the queue. With `huey.MemoryHuey` and `immediate: True`, the blueprint's default outside `prod`, tasks run inline in the web process and no worker is needed. With `SqliteHuey` or `RedisHuey` (the blueprint uses Redis in `prod`), tasks wait in the queue until a worker runs them; if no worker is running, they never run. The [Background Tasks guide](/docs/tasks) covers the backends, retries and periodic tasks.

---

## Deploy checklist

On each deploy, in this order:

1. **Build the new image.** `docker compose build`, or `docker build -t myapp:latest .`.
2. **Check the pending migrations.** `proper db todo` lists the ones not yet applied to the `main` database.
3. **Migrate before starting the new version.** `docker compose run --rm migrate`, or `proper db migrate`. The old version keeps serving while this runs, so write migrations the old code can live with: add columns before using them, remove them after the code stops using them. See [Migrations](/docs/migrations).
4. **Restart the web server and the worker.** `docker compose up -d web worker`.
5. **Check the health.** `docker compose ps` shows the health of `web`, from the `/up` check. You can also request `/up` yourself.
6. **Read the logs.** `docker compose logs -f web worker`. A failed start, such as the GIL check or a bad config, shows up here.

---

## Performance

How fast is this? The table below was measured on 2026-09-25 on an Intel Core i5-14400 (6 performance and 4 efficiency cores), with 64 connections, all rows from the same run. The Python servers ran Granian with 4 workers of 4 threads, 16 threads in total; Proper's second row is 2 processes of 2 workers of 4 threads. Go and Rust used every core.

| server | plaintext rps | json rps | fortunes rps | fortunes p50 | fortunes p99 | RSS |
|---|---:|---:|---:|---:|---:|---:|
| Proper 0.26, Granian WSGI | 115,658 | 108,283 | 35,014 | 1.7 ms | 4.2 ms | 186 MB |
| Proper 0.26, 2 processes | 130,486 | 116,711 | 34,217 | 1.7 ms | 4.3 ms | 306 MB |
| Flask 3.1 + SQLAlchemy, Granian WSGI | 78,419 | 71,957 | 13,871 | 3.0 ms | 41.3 ms | 190 MB |
| Django 6.1, Granian WSGI | 54,888 | 51,559 | 10,252 | 5.8 ms | 32.1 ms | 157 MB |
| FastAPI 0.141 + SQLAlchemy, Granian ASGI | 46,025 | 41,236 | 11,570 | 3.4 ms | 60.6 ms | 311 MB |
| Rails 8.1, Puma | 9,772 | 10,398 | 6,584 | 9.6 ms | 13.5 ms | 492 MB |
| Beego 2.3 (Go) | 319,266 | 286,463 | 35,380 | 1.1 ms | 9.3 ms | 62 MB |
| Actix Web 4.15 + sqlx (Rust) | 681,178 | 682,365 | 51,656 | 1.1 ms | 3.5 ms | 19 MB |
| Topcoat 0.9 + Toasty (Rust) | 421,616 | 424,008 | 198,484 | 0.3 ms | 0.8 ms | 17 MB |

`plaintext` and `json` return a fixed response, so they measure the fixed cost of each request. `fortunes` reads 12 rows from SQLite, adds one, sorts them and renders a template; it is the one that resembles a real page.

What the table shows:

- On pages with a database and a template, Proper is even with Go's Beego and ahead of the other Python and Ruby frameworks, with a lower tail latency (p99) than any of them.
- On trivial routes, Proper is 2.5 to 3 times behind Go. That gap is the cost of running Python for each request.
- The second process adds about 13% on plaintext and nothing on fortunes, for 120 MB more memory. That is why `PROCESSES` defaults to 1.
- Numbers move between runs: Proper's plaintext within about 10%, Beego's fortunes between 31k and 36k requests per second.

The benchmark code, the setup for every framework, and the instructions to reproduce these numbers on your machine are in the [proper-bench repository](https://github.com/jpsca/proper-bench){target=_blank}.

---

## What's next

Deployment touches several other parts of Proper:

- [Background Tasks](/docs/tasks) - the queue backends, the worker, retries and periodic tasks.
- [Channels](/docs/channels) - the cable process, broadcasting, and `RedisCable` for several machines.
- [Migrations](/docs/migrations) - creating and running the migrations you apply on each deploy.
- [Assets](/docs/assets) - fingerprinted assets and letting the proxy serve files.
- [Storage](/docs/storage) - uploads, the `storage/` directory and serving files through the proxy.
