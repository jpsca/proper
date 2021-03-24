"""
This file connects the application to the routes and error handlers.
"""
from liquid_orm.exceptions.orm import ModelNotFound
from proper import errors

from .app import app
from .models import db
from .routes import routes


app.routes = routes

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
app.errorhandler(errors.NotFound, "Pages.not_found")
app.errorhandler(ModelNotFound, "Pages.not_found")
app.errorhandler(Exception, "Pages.error")


@app.on_error
def on_error(req, resp, app):
    pass


@app.on_teardown
def on_teardown(req, resp, app):
    db.disconnect()
