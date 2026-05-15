[% if tailwind -%]
import subprocess

from ..main import app


class AppCLI(app.CLI):
    """Custom commands for this application"""
    def run(self):
        subprocess.Popen([
            "tailwindcss",
            "-i", "[[app_name]]/assets/styles/_tw.css",
            "-o", "[[app_name]]/assets/styles/app.css",
            "--watch",
        ], process_group=0)
        super().run()   # type: ignore

[% else %]
from ..main import app


class AppCLI(app.CLI):
    """Custom commands for this application"""
    pass
[% endif %]
