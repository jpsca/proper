import socket
import subprocess
import typing as t
from functools import wraps
from pathlib import Path

from proper_cli import Cli

if t.TYPE_CHECKING:
    from proper import App


UWSGI_DEV_CONFIG = "uwsgi-dev.ini"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 2300
WELCOME = """
   ┌─────────────────────────────────────────────────┐
   │   Running on:                                   │
   │   - Your machine:  {local}│
   │   - Your network:  {network}│
   │                                                 │
   │   Press `ctrl+c` to quit.                       │
   └─────────────────────────────────────────────────┘
"""
EXAMPLE_COM_IP = "93.184.216.34"


def get_app_cli(app: "App") -> t.Type[Cli]:
    attrs: dict[str, t.Any] = {
        "__doc__": """
        Application-specific commands.

        You don't need a special console to interact with the app,
        just run `ipython` or the regular python interpreter and import
        the application, like a regular python package.
        """,
        "run": get_run_server(app),
        "routes": get_routes_cmd(app),
        "credentials": get_credentials_cmd(app),
        "static": get_static_cli(app),
        "g": get_generators_cli(app),
        "install": get_install_cli(app),
        "welcome": welcome,
    }

    return type("AppCli", (Cli,), attrs)


def get_run_server(app: "App") -> t.Callable:
    def run_server(_self):
        """Runs the development server.

        Read the uWSGI config from `uwsgi-dev.ini`.
        """
        if not Path(UWSGI_DEV_CONFIG).exists():
            print(f"💥 {UWSGI_DEV_CONFIG} not found.")
            print("💥 Check you are in the root folder of your application.")
            return

        cmd = f"uwsgi --ini {UWSGI_DEV_CONFIG}"
        print(cmd)
        app.start()
        try:
            subprocess.check_call(cmd, shell=True)
        except KeyboardInterrupt:
            raise
        finally:
            app.shutdown()

    return run_server


def get_routes_cmd(app: "App") -> t.Callable:
    def routes(_self):
        """Show all registered routes."""
        print(
            "\nRoutes match in priority from top to bottom.\n"
            "The rules that doesn't have a `to` property are"
            " build-only and never match.\n"
        )

        routes = []
        for route in app.routes:
            method = route.method if route.method else "—"
            path = route.path
            if route.redirect:
                to = f"↪ {route.redirect}"
            elif route.to:
                to = route.to.__qualname__
            else:
                to = "-"
            name = route.name or "-"
            defaults = route.defaults or "-"
            routes.append([method, path, to, name, defaults])

        PADDING = 1
        HEADERS = ["", "PATH", "TO", "NAME", "DEFAULTS"]

        lengths = [len(header) for header in HEADERS]
        for route in routes:
            lengths = [max(ll, len(text)) for ll, text in zip(lengths, route)]
        lengths = [ll + PADDING for ll in lengths]

        print(*[header.ljust(ll, " ") for (header, ll) in zip(HEADERS, lengths)])
        print(*["-" * ll for ll in lengths])
        for route in routes:
            print(*[text.ljust(ll, " ") for (text, ll) in zip(route, lengths)])
        print()

    return routes


def get_credentials_cmd(app: "App") -> t.Callable:
    def credentials(_self, env="production"):
        """Edit your encrypted credentials.

        Arguments:

        - env:
            Name of the environment (e.g.: "production"). It will be used
            for finding the encrypted file ("production.enc.yaml").

        """
        app.edit_credentials(env)

    return credentials


def get_generators_cli(app: "App") -> t.Type[Cli]:
    from . import generators

    attrs: dict[str, t.Any] = {
        "__doc__": """Generate new code.""",
    }

    for name in ("resource", "controller", "model"):
        attrs[name] = _get_cmd(app, generators, f"gen_{name}")

    return type("Generators", (Cli,), attrs)


def get_static_cli(app: "App") -> t.Type[Cli]:
    from . import assets

    attrs: dict[str, t.Any] = {
        "__doc__": """Manage assets.""",
    }

    for name in ("bundle", "build", "clean"):
        attrs[name] = _get_cmd(app, assets, name)

    return type("Assets", (Cli,), attrs)


def get_install_cli(app: "App") -> t.Type[Cli]:
    from . import auth, storage

    attrs: dict[str, t.Any] = {
        "__doc__": "",
        "auth": _get_cmd(app, auth, "install"),
        "storage": _get_cmd(app, storage, "install"),
        # "text": _get_cmd(app, text, "install"),
    }
    return type("Install", (Cli,), attrs)


def welcome(_self, host="0.0.0.0", port=2300) -> None:
    """Display the welcome message for the development server.

    Arguments:

    - host [0.0.0.0]
    - port [2300]

    """
    local = "{:<29}".format(f"http://{host}:{port}")
    network = "{:<29}".format(f"http://{_get_local_ip()}:{port}")

    print(WELCOME.format(local=local, network=network))


def _get_cmd(app, module: t.Any, name: str) -> t.Callable:
    func = getattr(module, name)

    @wraps(func)
    def cmd(_, *args, **kw):
        return func(app, *args, **kw)

    return cmd


def _get_local_ip() -> str:
    ip = socket.gethostbyname(socket.gethostname())
    if not ip.startswith("127."):
        return ip
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        sock.connect((EXAMPLE_COM_IP, 1))
        ip = sock.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip
