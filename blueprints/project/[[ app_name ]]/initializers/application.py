import proper

from ..app import app
from ..controllers import Pages
from ..models import db


# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
app.error_handler(proper.errors.NotFound, Pages.not_found)
app.error_handler(Exception, Pages.error)


@app.on_error
def rollback_db_session(req, resp):
    db.s.rollback()


@app.on_teardown
def remove_db_session(req, resp):
    db.s.remove()
