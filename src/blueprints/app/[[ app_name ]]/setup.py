import subprocess
import sys
from importlib import import_module

import proper

from .app import app, config
from .cl import AppCL
from .views.page import Page


app.CL = AppCL

if app.catalog:
    app.catalog.add_folder(app.components_path / "common")


# ---- Database ----

@app.on_error
def on_error():
    if app.db and not app.db.is_closed():
        app.db.rollback()


@app.on_teardown
def on_teardown():
    if app.db and not app.db.is_closed():
        app.db.close()


# ---- Error handlers ----

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
#
# If `app.config.DEBUG = True`, this also will create test routes
# (based on the name of the exception class) to preview those pages
# so you can test their design.
app.error_handler(proper.errors.NotFound, Page.not_found)  # /_not_found
app.error_handler(Exception, Page.error)  # /_exception


# ---- Development ----

@app.on_dev_start
def compile_tailwind():
    from pytailwindcss import get_bin_path

    cmd = [
        str(get_bin_path()),
        "-i",
        "static_src/css/app.css",
        "-o",
        "static/css/app.css",
        "--watch",
    ]
    scmd = " ".join(cmd)
    print("Running",f'"{scmd}"')
    subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
