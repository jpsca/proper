"""This file connects the application to the routes and error handlers.
"""
from proper import errors

from .app import app
from .controllers import Pages
from .models import dbs
from .routes import routes


app.routes = routes

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
app.errorhandler(errors.NotFound, Pages.not_found)
app.errorhandler(Exception, Pages.error)


@app.on_error
def rollback_db_session(app, req, resp):
    dbs.rollback()


@app.on_teardown
def remove_db_session(app, req, resp):
    dbs.commit()
    dbs.close()
