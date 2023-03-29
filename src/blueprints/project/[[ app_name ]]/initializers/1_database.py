from ..app import app, config


if config.database.engine == "postgres":
    from playhouse.postgres_ext import PostgresqlExtDatabase

    app.db = PostgresqlExtDatabase(
        config.database.name,
        host=config.database.host,
        port=config.database.port,
        user=config.database.user,
        password=config.database.password,
        # The connection is managed in the `on_before_dispatch`,
        # `on_teardown`, and `on_error` hooks
        autoconnect=False,
    )

else:
    from playhouse.sqlite_ext import SqliteExtDatabase

    app.db = SqliteExtDatabase(f"{config.database.name}.sqlite")


@app.on_before_dispatch
def on_before_dispatch(req, resp):
    if app.db:
        if not app.db.is_closed():
            app.db.close()
        app.db.connect()


@app.on_error
def on_error(req, resp):
    if app.db and not app.db.is_closed():
        app.db.rollback()


@app.on_teardown
def on_teardown(req, resp):
    if app.db and not app.db.is_closed():
        app.db.close()
