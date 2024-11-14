from .app import app
from .cl import AppCL


app.CL = AppCL

if app.catalog:
    app.catalog.add_folder(app.views_path / "common")


# ---- Database ----

@app.on_error
def on_error():
    if app.db and not app.db.is_closed():
        app.db.rollback()


@app.on_teardown
def on_teardown():
    if app.db and not app.db.is_closed():
        app.db.close()


# ---- Development ----

# @app.on_dev_start
# def compile_tailwind():
#     from pytailwindcss import get_bin_path

#     cmd = [
#         str(get_bin_path()),
#         "-i",
#         "static_src/css/app.css",
#         "-o",
#         "static/css/app.css",
#         "--watch",
#     ]
#     scmd = " ".join(cmd)
#     print("Running",f'"{scmd}"')
#     subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
