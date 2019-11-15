from .core import BLUEPRINTS, core, import_app  # noqa
from .new import *  # noqa
from .secrets import *  # noqa
from .run import *  # noqa


def start_cli():
    # TODO: get app commands
    return core.run()


if __name__ == "__main__":
    start_cli()
