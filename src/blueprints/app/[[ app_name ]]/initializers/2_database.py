from importlib import import_module

from ..app import app, config


db_config = config.DATABASE_ENGINES[config.DATABASE].copy()
mod_name, cls_name = db_config.pop("type").rsplit(".", 1)
mod = import_module(mod_name)
Cls = getattr(mod, cls_name)
app.db = Cls(**db_config)


@app.on_error
def on_error():
    if app.db and not app.db.is_closed():
        app.db.rollback()


@app.on_teardown
def on_teardown():
    if app.db and not app.db.is_closed():
        app.db.close()
