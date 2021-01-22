"""This file connects the application to the routes and error handlers.
"""
import sentry_sdk
from proper import errors

from [[ name ]].config import env
from [[ name ]].adapters import db
from .app import app
from .routes import routes


if env == "production":
    import sentry_sdk
    from sentry_sdk.integrations.wsgi import SentryWsgiMiddleware
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn="https://c1710b13b5014115a56e9611e8f71b2c@o452745.ingest.sentry.io/5518830",
        integrations=[
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        environment=env,
    )
    app.wsgi_app = SentryWsgiMiddleware(app.wsgi_app)

app.routes = routes

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
app.errorhandler(errors.NotFound, "Pages.not_found")
app.errorhandler(Exception, "Pages.error")


@app.on_error
def rollback_on_error(req, resp, app):
    db.rollback()
    sentry_sdk.set_user(req.user)
    sentry_sdk.set_context("environ", req.environ)
    sentry_sdk.set_context("error", resp.error)



@app.on_teardown
def teardown_db(req, resp, app):
    db.remove()
