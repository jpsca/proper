from . import models  # noqa
from .app import app
from .db import db
from .routes import routes

app.routes = routes
db.generate_mapping(create_tables=True)
