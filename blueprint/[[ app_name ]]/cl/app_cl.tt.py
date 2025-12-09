[% if use_tailwindcss -%]
import subprocess

from ..main import app


class AppCL(app.CL):
    """Custom commands for this application"""
    def run(self):
        subprocess.Popen([
            "tailwindcss",
            "-i", "static/css/_input.css",
            "-o", "static/css/styles.css",
            "--watch",
        ], process_group=0)
        super().run()   # type: ignore

[% else %]
from ..main import app


class AppCL(app.CL):
    """Custom commands for this application"""
    pass
[% endif %]
