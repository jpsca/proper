from proper import App

from . import config


app = App(__name__, config)
config = app.config

