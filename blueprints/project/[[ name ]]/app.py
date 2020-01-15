import logging
import os
from pathlib import Path

from proper import App, errors
from whitenoise import WhiteNoise


root_path = Path(__name__).parent.parent
env = os.getenv("PROPER_ENV", "development")

app = App(
    __name__,
    config=[
        f"{root_path}/config/common.yaml",
        f"{root_path}/config/{env}/config.yaml",
    ],
    secrets=[f"{root_path}/config/{env}/secrets.yaml.enc",],
)

config = app.config

if app.debug:
    logging.getLogger().setLevel(logging.DEBUG)

# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError`.
app.errorhandler(errors.NotFound, "Pages.not_found")
app.errorhandler(errors.ServerError, "Pages.error")

# Serve static files, even in production (but also use a CDN in production).
# Please read: http://whitenoise.evans.io
static_path = (root_path / "static").resolve()
app.wsgi = WhiteNoise(
    app.wsgi, root=static_path, autorefresh=config.debug, allow_all_origins=True,
)
