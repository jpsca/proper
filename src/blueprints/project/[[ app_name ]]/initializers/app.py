import proper
from playhouse.postgres_ext import PostgresqlExtDatabase

from ..app import app, config, scheduler
from ..controllers import Page


app.db = PostgresqlExtDatabase(
    name=config.db.name,
    host=config.db.host,
    port=config.db.port,
    user=config.db.user,
    password=config.db.password,
)

app.on_before_dispatch(app.db.connect)
app.on_error(app.db.rollback)
app.on_teardown(app.db.close)

scheduler.pre_execute(app.db.connect)
scheduler.post_execute(app.db.close)

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
#
# If `app.config.debug = True`, this also will create test routes
# (based on the name of the exception class) to preview those pages
# so you can test their design.
app.error_handler(proper.errors.NotFound, Page.not_found)  # /_not_found
app.error_handler(Exception, Page.error)  # /_exception

