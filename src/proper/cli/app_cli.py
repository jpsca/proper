import typing as t
from functools import wraps

from proper_cli import Cli

from .db_cli import get_db_cli


if t.TYPE_CHECKING:
    from ..app import App


def get_cli(app: "App") -> type[Cli]:
    attrs: dict[str, t.Any] = {
        "__doc__": """
        Application-specific commands.

        You don't need a special console to interact with the app,
        just run `ipython` or the regular python interpreter and import
        the application, like a regular python package.
        """,
        "run": get_run_cli(app),
        "routes": get_routes_cmd(app),
        "db": get_db_cli(app),
        "g": get_generators_cli(app),
        "install": get_install_cli(app),
    }

    return t.cast(type[Cli], type("appCL", (Cli,), attrs))


def get_run_cli(app: "App") -> t.Callable:
    def run(self, config="uvicorn.dev.py"):
        """Run the development server.

        Arguments:
            config ["uvicorn.dev.py"]:
                A Python file whose module-level variables are passed
                as keyword arguments to `uvicorn.run()`.

        """
        import importlib.util

        import uvicorn

        from ..helpers import show_banner, show_welcome

        spec = importlib.util.spec_from_file_location("_uvicorn_config", config)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        kwargs = {
            k: v for k, v in vars(mod).items()
            if not k.startswith("_")
        }

        kwargs["host"] = "0.0.0.0"
        kwargs["port"] = int(app.config["PORT"] or "2300")
        show_banner()
        show_welcome(app.config["HOST"])
        uvicorn.run(**kwargs)

    return run

def get_routes_cmd(app: "App") -> t.Callable:
    def routes(self):
        """Show all registered routes."""
        print(
            "\nRoutes match in priority from top to bottom.\n"
            "The rules that don't have a `to` property are"
            " build-only and never match.\n"
        )

        routes = []
        for route in app.routes:
            method = route.method if route.method else "-"
            path = route.path
            if route.redirect:
                to = f"↪ {route.redirect}"
            elif route.to:
                mod = route.to.__module__
                prefix = ""
                if ".controllers." in mod:
                    parts = mod.split(".controllers.", 1)[1]
                    segments = parts.split(".")
                    if len(segments) > 1:
                        prefix = "/".join(segments[:-1]) + "/"
                to = prefix + route.to.__qualname__
            else:
                to = "-"
            name = route.name or "-"
            host = route.host or "-"
            routes.append([method, path, to, name, host])

        PADDING = 1
        HEADERS = ["", "PATH", "TO", "NAME", "HOST"]

        lengths = [len(header) for header in HEADERS]
        for route in routes:
            lengths = [
                max(ll, len(text)) for ll, text in zip(lengths, route, strict=False)
            ]
        lengths = [ll + PADDING for ll in lengths]

        print(
            *[
                header.ljust(ll, " ")
                for (header, ll) in zip(HEADERS, lengths, strict=False)
            ]
        )
        print(*["-" * ll for ll in lengths])
        for route in routes:
            print(
                *[text.ljust(ll, " ") for (text, ll) in zip(route, lengths, strict=False)]
            )
        print()

    return routes


def get_generators_cli(app: "App") -> type[Cli]:
    from .. import generators

    attrs: dict[str, t.Any] = {
        "__doc__": """Generate new code.""",
    }

    for name in ("resource", "model", "controller", "email", "seed"):
        attrs[name] = _get_cmd(app, generators, f"gen_{name}")

    return t.cast(type[Cli], type("Generators", (Cli,), attrs))


def get_install_cli(app: "App") -> type[Cli]:
    from proper.install import auth, channels, i18n, storage

    attrs: dict[str, t.Any] = {
        "__doc__": "",
        "auth": _get_cmd(app, auth, "install"),
        "i18n": _get_cmd(app, i18n, "install"),
        "storage": _get_cmd(app, storage, "install"),
        "channels": _get_cmd(app, channels, "install"),
        # "text": _get_cmd(app, text, "install"),
    }
    return t.cast(type[Cli], type("Install", (Cli,), attrs))


def _get_cmd(app, module: t.Any, name: str) -> t.Callable:
    func = getattr(module, name)
    @wraps(func)
    def cmd(_, *args, **kw):
        return func(app, *args, **kw)

    return cmd
