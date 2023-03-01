from proper.scheduler import HueyScheduler

from ..app import app, config


app.scheduler = HueyScheduler(**config.scheduler)

app.on_dev_start(app.scheduler.start)
app.on_dev_shutdown(app.scheduler.shutdown)


@app.scheduler.on_startup()
def open_db_connection():
    if not app.db.is_closed():
        app.db.close()
    app.db.connect()
