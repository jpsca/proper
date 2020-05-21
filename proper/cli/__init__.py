from .core import BLUEPRINTS, core, import_cli, running_in_app  # noqa

if running_in_app:
    from .run import *  # noqa
    from .secret import *  # noqa
    from .generators import *  # noqa
else:
    from .new import *  # noqa
    from .secret import *  # noqa


def start():
    if running_in_app:
        cli = import_cli()
        if cli:
            core.merge(cli)
    return core.run()


if __name__ == "__main__":
    start()
