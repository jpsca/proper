from pathlib import Path

import pytest


APP_NAME = "app"

SCAF_VIEW = """from proper import Controller

class PagesController(Controller):
    def index(self):
        pass
"""

SCAF_ROUTES = """
routes = [
    get("", to=PagesController.index),
]

"""


@pytest.fixture()
def scaffold(tmp_path):
    app_root = Path(tmp_path) / APP_NAME
    (app_root / "controllers").mkdir(parents=True, exist_ok=True)
    (app_root / "views").mkdir(parents=True, exist_ok=True)
    (app_root / "controllers" / "__init__.py").touch()
    (app_root / "controllers" / "pages.py").write_text(SCAF_VIEW)
    (app_root / "routes.py").write_text(SCAF_ROUTES)
    return app_root
