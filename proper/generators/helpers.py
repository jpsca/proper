from pathlib import Path

from proper.helpers import BLUEPRINTS, render_folder as _render_folder


RULES_TMPL = BLUEPRINTS / "rules.py"


def get_extended_rules(app, actions):
    rules = (app.root_path / "rules.py").read_text()


def render_folder(src, dst, data):
    envops = {
        "block_start_string": "[%",
        "block_end_string": "%]",
        "variable_start_string": "[[",
        "variable_end_string": "]]",
    }
    return _render_folder(src, dst, data, envops=envops)
