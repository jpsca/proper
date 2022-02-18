from .app import app
from .routes import routes

app.routes = routes

from . import initializers, models, cli  # noqa
