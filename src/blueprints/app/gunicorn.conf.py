import multiprocessing
import subprocess
import sys

from proper.helpers import show_welcome

from wsgi import app


HOST = "0.0.0.0"
PORT = "2300"


wsgi_app = "wsgi:app"
bind = f"{HOST}:{PORT}"

if app.config.DEBUG:
    reload = True
    reload_extra_files = [*app.get_components_folders()]

workers = multiprocessing.cpu_count()
# workers = multiprocessing.cpu_count() * 2

# Needed for websockets
worker_class = "gevent"

# The number of pending connections. This refers
# to the number of clients that can be waiting to be
# served. Exceeding this number results in the client
# getting an error when attempting to connect. It should
# only affect servers under significant load.
# Must be a positive integer. Generally set in the 64-2048 range.
backlog = 2048

# "-" means log to stdout.
errorlog = "-"
loglevel = "warning"

# "-" means log to stdout.
accesslog = "-"
if app.config.DEBUG:
    access_log_format = '%(h)s "%(r)s" [%(s)s %(b)sB, %(M)sms]'


def on_starting(server):
    """Called just before the master process is initialized."""
    if app.config.DEBUG:
        _compile_tailwind()


def when_ready(server):
    """Called just after the server is started."""
    server.log.debug("Server is ready. Spawning workers")
    if app.config.DEBUG:
        show_welcome(HOST, PORT)


def on_reload(server):
    """Called to recycle workers during a reload."""
    show_welcome(HOST, PORT)


def on_exit(server):
    """Called just before exiting Gunicorn."""
    if app.config.DEBUG:
        print("✨ Goodbye ✨")


def _compile_tailwind():
    cmd = [
        "tailwindcss",
        "-i",
        "static_src/css/app.css",
        "-o",
        "static/css/app.css",
        "--watch",
    ]
    try:
        print(" ".join(cmd))
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    finally:
        if proc:
            proc.kill()
