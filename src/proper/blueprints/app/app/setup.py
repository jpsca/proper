from .cl import AppCL
from .main import app


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
