from proper import App

from .config import config


app = App(__name__, config)
config = app.config
