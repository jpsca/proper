import playhouse

from ..app import app, config


db_config = config.DATABASE_ENGINES[config.DATABASE].copy()
Cls = getattr(playhouse, db_config.pop("type"))
app.db = Cls(**db_config)


@app.on_error
def on_error(req, resp):
    if app.db and not app.db.is_closed():
        app.db.rollback()


@app.on_teardown
def on_teardown(req, resp):
    if app.db and not app.db.is_closed():
        app.db.close()
