"""This file connects the application to the routes and error handlers.
"""
from proper import errors

from .adapters import db
from .app import app
from .routes import routes


app.routes = routes

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
app.errorhandler(errors.NotFound, "Pages.not_found")
app.errorhandler(Exception, "Pages.error")


@app.on_error
def rollback_on_error(req, resp, app):
    db.rollback()


@app.on_teardown
def teardown_db(req, resp, app):
    db.remove()
