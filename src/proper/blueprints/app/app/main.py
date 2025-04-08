import jinjax_ui
from proper import App

from .config import config


app = App(__name__, config)
config = app.config

app.catalog..add_folder(jinjax_ui.components_path, prefix="ui")
