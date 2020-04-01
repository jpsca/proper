from .core import BLUEPRINTS, core, import_cli  # noqa
from .generators import *  # noqa
from .new import *  # noqa
from .run import *  # noqa


def start():
    cli = import_cli()
    if cli:
        core.merge(cli)
    return core.run()


if __name__ == "__main__":
    start()
