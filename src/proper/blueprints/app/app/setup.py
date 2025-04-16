import jinjax_ui

from .cl import AppCL
from .main import app


app.CL = AppCL

app.catalog.add_folder(jinjax_ui.components_path, prefix="ui")
