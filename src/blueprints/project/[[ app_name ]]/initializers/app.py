import proper
from proper import HueyScheduler
from playhouse.postgres_ext import PostgresqlExtDatabase

from ..app import app, config
from ..controllers import Page


app.db = PostgresqlExtDatabase(
    config.database.name,
    host=config.database.host,
    port=config.database.port,
    user=config.database.user,
    password=config.database.password,
)

app.scheduler = HueyScheduler(**config.scheduler)


@app.on_before_dispatch
def on_before_dispatch(req, resp):
    if app.db:
        app.db.connect()


@app.on_error
def on_error(req, resp):
    if app.db:
        app.db.rollback()


@app.on_teardown
def on_teardown(req, resp):
    if app.db:
        app.db.close()


app.on_dev_start(app.scheduler.start)
app.on_dev_shutdown(app.scheduler.shutdown)

app.scheduler.pre_execute(app.db.connect)
app.scheduler.post_execute(app.db.close)


# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
#
# If `app.config.debug = True`, this also will create test routes
# (based on the name of the exception class) to preview those pages
# so you can test their design.
app.error_handler(proper.errors.NotFound, Page.not_found)  # /_not_found
app.error_handler(Exception, Page.error)  # /_exception
