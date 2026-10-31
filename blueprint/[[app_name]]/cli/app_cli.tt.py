[% if tailwind -%]
import subprocess
import typing as t

from ..main import app


if t.TYPE_CHECKING:
    from proper_cli import Cli as _BaseCLI
else:
    _BaseCLI = app.CLI


class AppCLI(_BaseCLI):
    """Custom commands for this application"""
    def run(self):
        subprocess.Popen([
            "tailwindcss",
            "-i", "assets/css/_tw.css",
            "-o", "assets/css/app.css",
            "--watch",
        ], process_group=0)
        super().run()   # type: ignore

[% else %]
import typing as t

from ..main import app


if t.TYPE_CHECKING:
    from proper_cli import Cli as _BaseCLI
else:
    _BaseCLI = app.CLI


class AppCLI(_BaseCLI):
    """Custom commands for this application"""
    pass
[% endif %]
