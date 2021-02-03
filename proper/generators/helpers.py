from pathlib import Path

from proper.helpers import BLUEPRINTS


RULES_TMPL = BLUEPRINTS / "rules.py"


def get_extended_rules(app, actions):
    rules = (app.root_path / "rules.py").read_text()
