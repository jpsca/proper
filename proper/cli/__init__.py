from .core import BLUEPRINTS, core, import_app  # noqa
from .generators import *  # noqa
from .new import *  # noqa
from .run import *  # noqa
from .secrets import *  # noqa


def start_cli():
    app = import_app()
    if app:
        cli = getattr(app, "cli", None) or {}
        for group, commands in cli.items():
            core.add_commands(commands, group=group)
    return core.run()


if __name__ == "__main__":
    start_cli()
