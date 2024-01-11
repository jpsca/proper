from pathlib import Path

import pytest


APP_NAME = "app"

SCAF_CONTROLLER = """from proper import Controller

class Pages(Controller):
    def index(self):
        pass
"""

SCAFF_ROUTES = """
routes = [
    get("", to=Pages.index),
]

"""


@pytest.fixture()
def scaffold(tmp_path):
    app_root = Path(tmp_path) / APP_NAME
    (app_root / "controllers").mkdir(parents=True, exist_ok=True)
    (app_root / "components").mkdir(parents=True, exist_ok=True)
    (app_root / "controllers" / "__init__.py").touch()
    (app_root / "controllers" / "pages.py").write_text(SCAF_CONTROLLER)
    (app_root / "routes.py").write_text(SCAFF_ROUTES)
    return app_root
