---
title: Deployment
description: Running a Proper app in production: free-threaded Python, what runs (web, cable, worker, migrations, proxy), sizing WORKERS/MAX_THREADS/PROCESSES, the prod config and .env, compiled views, the Dockerfile, compose.yml, the nginx config, trusted proxies, the deploy checklist
last_verified: 2026-11-08
sources:
  - blueprint/Dockerfile.tt
  - blueprint/Dockerfile.tt.workers
  - blueprint/compose.tt.yml
  - blueprint/deploy
  - blueprint/.env.tt.example
  - blueprint/workers.tt.py
  - blueprint/[[app_name]]/config
---

# Deployment

A new app already has every file a deploy needs: `Dockerfile`, `Dockerfile.workers`, `compose.yml`, `deploy/nginx.conf`, `.env.example` and `workers.py`. This doc says what each one does and which settings matter, so you change them with a reason instead of rewriting them. What `proper run` starts and how the app logs are in [cli.md](cli.md); the forwarding headers in depth are in [security.md](security.md#trusted-proxies).

## Table of Contents

- [Requirements](#requirements)
- [What Runs in Production](#what-runs-in-production)
- [Sizing](#sizing)
- [Production Configuration](#production-configuration)
- [Compiled Views](#compiled-views)
- [Docker](#docker)
- [Compose](#compose)
- [The Reverse Proxy (nginx)](#the-reverse-proxy-nginx)
- [Background Workers](#background-workers)
- [Deploy Checklist](#deploy-checklist)


## Requirements

- **Linux.** WSL on Windows; a container on macOS (the blueprint's `Dockerfile`).
- **Free-threaded Python**, the `t` builds: `3.14t`. The blueprint pins it in `.python-version` and allows `>=3.14,<4` in `pyproject.toml`. Install it with `uv python install 3.14t`. Threads of one process run Python in parallel, so one interpreter with one copy of the app serves many requests at once.
- `proper run` **refuses to start on a Python with the GIL**. A free-threaded Python turns the GIL back on when it imports an extension module that has not declared itself safe; Python names the module in a `RuntimeWarning` and `proper run` stops with the same message. Fix: upgrade or replace that module. Last resort: `ALLOW_GIL = True` in the config serves with the GIL (threads no longer run in parallel; you need more `PROCESSES` and memory to get the throughput back).
- **No ASGI, no middleware.** TLS and compression belong to the reverse proxy; cross-cutting app behavior goes in callbacks and concerns ([concerns.md](concerns.md)).


## What Runs in Production

| Process | Command | Notes |
|---|---|---|
| Web server | `proper run` | Bearings on `0.0.0.0:PORT` (2300). With channels, it also serves the WebSockets on `CABLE_PORT` (2301, `PORT + 1`) from the same process. `--host`, `--port`, `--workers` override the config. |
| Background worker | `python workers.py` | The Huey consumer, from the **same image** as the web server. Needed only when `QUEUE` is Redis or SQLite (in `prod` the blueprint uses `RedisHuey`); with `MemoryHuey` + `immediate: True` tasks run inline. |
| Migrations | `proper db prepare` | One-off job before starting the new version: `proper db migrate` for every database, then `proper db seed`. Never on every container start. |
| Reverse proxy | nginx | Terminates TLS, serves `assets/` from disk, routes `/cable` to `CABLE_PORT`, passes `Host` and the `X-Forwarded-*` headers. |

Broadcasts made outside the web process (the worker, extra `PROCESSES`, a shell) are forwarded to it as a signed `POST` on `127.0.0.1:CABLE_PORT + 1`; if that process is down the message is lost and a warning logged. On several machines use `RedisCable` ([cable.md](cable.md#several-machines-rediscable)).

Every new app has a `GET /up` route (`PublicController.health`, route `Public.health`, returns 200 when serving): the Docker `HEALTHCHECK` and the load balancer use it. With channels, `app.cable.health()` reports the WebSockets and `127.0.0.1:CABLE_PORT + 1/metrics` serves Prometheus text ([cable.md](cable.md#cable-bearings)).


## Sizing

| Setting | Default | Blueprint reads it from | What it controls |
|---|---|---|---|
| `PORT` | `2300` | `PORT` | The port the server binds to |
| `WORKERS` | `1` | `WORKERS` | Threads that read and write the network, per process. They never run your code |
| `MAX_THREADS` | `0` = `min(32, cpus + 4)` | — | Threads that run your code per process = requests handled at once = **database connections held** per process |
| `PROCESSES` | `1` | `PROCESSES` | Copies of the web server on the same port (`SO_REUSEPORT`) |
| `CABLE_PORT` | `0` (none) | `CABLE_PORT` | Port of the WebSockets; the channels addon sets `PORT + 1` |
| `RELOAD` | `None` (follows `DEBUG`) | — | Restart on code changes; off in production |
| `LOG_FORMAT` | `None` (follows `DEBUG`) | — | `"json"` in production, `"console"` with `DEBUG`, `"off"` |
| `LOG_LEVEL` | `"info"` | — | Lowest level of the `proper` logger |

Starting points, then measure with your own pages:

- Small server: `WORKERS=1`, `PROCESSES=1`.
- Four or more cores: `WORKERS=4`; with memory to spare, `PROCESSES=2` (a second copy of the app in memory, about 10% more throughput at 16 threads on a 10-core machine; threads of one interpreter still contend for shared objects).
- Keep `MAX_THREADS` at its default unless database connections are the limit; with several processes each has its own `MAX_THREADS` connections.
- SQLite allows one writer at a time: more threads help reads, not writes.


## Production Configuration

The config files branch on `APP_ENV` (`dev` default, `test`, `prod`). The Docker image sets `APP_ENV=prod`. In the `prod` branches of the blueprint:

| Setting | `prod` value |
|---|---|
| `DEBUG` | `False` (it is `env == "dev"`) |
| `PROTOCOL`, `HOST` | `"https"`, `"YOUR-DOMAIN.com"`. **Edit `HOST` before the first deploy**: absolute URLs (emails, `url_for(_full=True)`, storage URLs) are built from it, never from the request's `Host` |
| `SECRET_KEYS` | `os.getenv("SECRET_KEYS", "").split(",")` |
| `DATABASES["main"]` | `playhouse.postgres_ext.PooledPsycopg3Database` from `DB_*` (needs the `libpq5` system library; the image installs it) |
| `QUEUE` | `huey.RedisHuey` from `REDIS_*` (`uv add redis`); `QUEUE_CONSUMER["workers"]` = 4 |
| `CACHE` | `SqliteCache` at `storage/cache.sqlite3` (on the volume, shared by web and worker) |
| `MAILERS` | SMTP from `SMTP_USERNAME` / `SMTP_PASSWORD` |
| `STATIC_X_SENDFILE_HEADER` | `"X-Accel-Redirect"` (nginx). Apache/lighttpd: `"X-Sendfile"`. The app answers a file download with a header and the proxy sends the file, so a large download doesn't hold a thread |

If you keep SQLite in production, keep the file under `storage/` so it lives on the volume.

### Environment variables

`config/main.py` calls `load_dotenv(<project root>/.env)` at import, so the `.env` file works with and without Docker; a variable already in the environment is never replaced. The file is git-ignored and docker-ignored. Copy `.env.example` and fill it in:

| Variable | What it is |
|---|---|
| `SECRET_KEYS` | Comma-separated, oldest to newest, each 48+ random characters. Only the last signs, all verify: rotate by appending, remove the oldest once what it signed expired. **Never deploy with it empty** |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Postgres |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_NAME` | Redis, for the task queue |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | The SMTP mailer |
| `WEB_PORT` | Host port Compose publishes the web server on (the container listens on 2300) |
| `WORKERS`, `PROCESSES` | See [Sizing](#sizing) |


## Compiled Views

Views compile to Python modules under `_compiled/views/` next to the app package (`COMPILED_PATH` moves it; it is git-ignored). Outside `DEBUG`, a view that doesn't compile **stops the start**, listing every error, instead of failing its first request.

The `Dockerfile` compiles them at build time:

```dockerfile
RUN APP_ENV=dev .venv/bin/proper jx compile
```

It runs with the `dev` config because `prod` needs secrets that must not be in the image; the compiled output is the same unless `TEMPLATE_TAGS` differs by environment (then the app compiles again at start). Outside `DEBUG` the server doesn't recompile views that are already compiled, only checks that none is newer than its module, so the app starts faster and a broken view fails the build instead of the deploy. The `app` user must be able to write to `_compiled` for the cases where a view has to be compiled again.


## Docker

Two-stage image on `debian:trixie-slim`. The official `python` images have no free-threaded build, so uv installs the interpreter into `/python`, the same path in both stages, so the venv's links to it survive the copy. Trimmed:

```dockerfile {title="Dockerfile"}
ARG PYTHON_VERSION=3.14t
ARG UV_VERSION=0.13.1
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM debian:trixie-slim AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed UV_PYTHON=3.14t
RUN apt-get update && apt-get install --no-install-recommends -y gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*              # to compile psycopg[c]
RUN uv python install 3.14t
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./          # README.md: pyproject's `readme` needs it
RUN uv sync --frozen --no-install-project --no-dev # dependencies layer, cached until the lock changes
COPY . .
RUN uv sync --frozen --no-dev
RUN APP_ENV=dev .venv/bin/proper jx compile

FROM debian:trixie-slim AS runtime
COPY --from=builder /python /python
ENV APP_ENV=prod PORT=2300 VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates libpq5 libvips \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN mkdir -p storage log _compiled && chown -R app:app storage log _compiled
USER app
EXPOSE 2300 2301
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/up' % os.environ.get('PORT','2300'), timeout=2)" || exit 1
CMD ["proper", "run"]
```

- System libraries: `libpq5` for psycopg, `libvips` for image variants. The builder has `gcc`, `libc6-dev` and `libpq-dev` to compile `psycopg[c]`: `psycopg[binary]` has no wheels for free-threaded Python, and the blueprint's `pyproject.toml` suggests `psycopg[c,pool]`. The full file has `poppler-utils` (PDF previews) and `ffmpeg` (video previews) commented out; uncomment what [storage_advanced.md](storage_advanced.md) needs.
- The app runs as the unprivileged `app` user. `storage/` (uploads, SQLite files) and `log/` are its writable folders: mount volumes there. `.dockerignore` keeps `storage/*`, `.env`, `tests`, `_compiled` and the deploy files out of the image.
- **One image, three commands.** Web: `proper run`. Worker: `python workers.py`. Migrations: `proper db prepare` (or `proper db migrate`). Running the worker from the same image guarantees it imports the same tasks and models the web tier enqueues. `Dockerfile.workers` only exists to push a separate worker image to a registry: it builds `FROM` the app image, sets `HEALTHCHECK NONE` and the worker command.

```bash
docker build -t myapp:latest .
```


## Compose

`compose.yml` runs web and worker from the same image; Postgres and Redis are external, reached through `.env`:

```yaml {title="compose.yml"}
x-app: &app
  image: myapp:latest
  build: { context: ., dockerfile: Dockerfile }
  env_file: [.env]
  environment: { APP_ENV: prod }
  restart: unless-stopped

services:
  web:
    <<: *app
    ports: ["${WEB_PORT:-2300}:2300", "${CABLE_PORT:-2301}:2301"]
    volumes: [storage:/app/storage]
  worker:
    <<: *app
    command: ["python", "workers.py"]
    healthcheck: { disable: true }     # it serves no HTTP
    volumes: [storage:/app/storage]
  migrate:
    <<: *app
    command: ["proper", "db", "prepare"]
    restart: "no"
    profiles: ["tools"]                # `up` never starts it

volumes:
  storage:
```

The order, first time and on every deploy:

```bash
cp .env.example .env              # first time: fill in the secrets and hosts
docker compose build
docker compose run --rm migrate   # apply migrations (and seeds) once
docker compose up -d web worker
```


## The Reverse Proxy (nginx)

The app must not face the internet directly. `deploy/nginx.conf` has the full server block with the TLS lines commented out; its locations:

```nginx {title="deploy/nginx.conf"}
client_max_body_size 8M;            # keep in sync with MAX_CONTENT_LENGTH (8 MB default), or uploads the app accepts get a 413 here

# Fingerprinted assets: drop the hash, serve from disk, cache for a year
location ~* "^/assets/(.*)-[a-f0-9]{12,}\.([a-z0-9]+)$" {
  root /var/www/myapp;
  try_files /assets/$1.$2 =404;
  add_header Cache-Control "public, max-age=31536000, immutable";
}
location /assets/ {                 # the other assets; `alias` must end with a slash, like the location
  alias /var/www/myapp/assets/;
  add_header Cache-Control "public, max-age=0, must-revalidate";
}

# WebSockets: the cable on CABLE_PORT. Remove the block if the app has no channels;
# change the location if you change CABLE_PATH.
location /cable {
  proxy_pass http://127.0.0.1:2301;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_read_timeout 1h;            # don't close idle connections
}

location / {
  proxy_pass http://127.0.0.1:2300;
  proxy_set_header Host $host;      # REQUIRED: nginx's default sends 127.0.0.1:2300, and host-constrained routes and OriginProtection compare with Host
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;   # overwrite, never append or pass the client's through
}

error_page 500 502 503 504 /500.html;   # served by nginx, so visitors see it when the app is down
location = /500.html { root /var/www/myapp/assets; }
```

Rules the proxy must follow, with the reasons in [security.md](security.md#trusted-proxies) and [security.md, Host header](security.md#host-header):

- **Pass the client's `Host`** (`proxy_set_header Host $host;`). The app never builds URLs from it (it uses `PROTOCOL`/`HOST` from the config), but routes with a `host` and `OriginProtection` compare with it.
- **Overwrite `X-Forwarded-Proto`** with the scheme nginx got the request on. It decides `request.is_secure` and the `Secure` flag of the session and auth cookies.
- **Drop headers with `_` in the name** (`X_Forwarded_For`). nginx does so by default: keep `underscores_in_headers off` and `ignore_invalid_headers on`.
- **Trusted proxies.** The forwarding headers are read only from peers in `TRUSTED_PROXIES`, by default every loopback, private and link-local address. That covers nginx on the same machine, container or VPC. If clients can reach the app from those networks, or a CDN / public load balancer sits in front of nginx, list the proxies' addresses explicitly, **every hop in the chain** (otherwise `remote_ip` is the CDN edge's address for every visitor and the default `rate_limit` puts them all in one bucket):

```python {title="config/main.py"}
TRUSTED_PROXIES = [
    "127.0.0.0/8", "::1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "173.245.48.0/20", "103.21.244.0/22",  # your CDN's published ranges
]
```

- **Request ID.** Every response carries `X-Request-ID`, the same id as the `request_id` of every log line written for it. To share one id with nginx's access log, add `proxy_set_header X-Request-ID $request_id;` and `$request_id` to nginx's `log_format`; the app keeps an incoming id (letters, digits, `-`, `_`, `@`, at most 200 characters).


## Background Workers

`python workers.py` starts Huey's `Consumer(app.queue, **QUEUE_CONSUMER)`. The options that matter for a deploy, in `config/storage.py`:

| Option | What it is |
|---|---|
| `workers` | Tasks run at once (the blueprint sets 4 in `prod`) |
| `worker_type` | `"thread"` (default), `"process"` or `"greenlet"` |
| `graceful_signal` | `"TERM"`: `docker stop` and most supervisors send SIGTERM, so a deploy lets running tasks finish |
| `shutdown_timeout` | Seconds to wait for running tasks on a graceful stop; `None` (default) waits |

If no worker runs with `RedisHuey` or `SqliteHuey`, enqueued tasks never run. Backends, retries and periodic tasks are in [tasks.md](tasks.md).


## Deploy Checklist

1. **Build** the new image: `docker compose build` (or `docker build -t myapp:latest .`).
2. **Check pending migrations**: `proper db todo`.
3. **Migrate before starting the new version**: `docker compose run --rm migrate`. The old version keeps serving meanwhile, so write migrations the old code can live with: add columns before using them, remove them after the code stops using them ([migrations.md](migrations.md)).
4. **Restart** web and worker: `docker compose up -d web worker`.
5. **Check health**: `docker compose ps` (the `/up` check), or request `/up`.
6. **Read the logs**: `docker compose logs -f web worker`. A failed start (the GIL check, a bad config, a view that doesn't compile) shows here. Production lines are JSON with a `request_id` ([cli.md](cli.md#logging)).
