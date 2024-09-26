import typing as t
from functools import wraps

from proper_cli import Cli

from .db_cl import get_db_cl


if t.TYPE_CHECKING:
    from proper import App


def get_app_cl(app: "App") -> t.Type[Cli]:
    attrs: dict[str, t.Any] = {
        "__doc__": """
        Application-specific commands.

        You don't need a special console to interact with the app,
        just run `ipython` or the regular python interpreter and import
        the application, like a regular python package.
        """,
        "routes": get_routes_cmd(app),
        "db": get_db_cl(app),
        "g": get_generators_cl(app),
        "install": get_install_cl(app),
    }

    return type("appCL", (Cli,), attrs)


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
            defaults = "{...} " if route.defaults else "-"
            routes.append([method, path, to, name, defaults])

        PADDING = 1
        HEADERS = ["", "PATH", "TO", "NAME", "DEFAULTS"]

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


def get_generators_cl(app: "App") -> t.Type[Cli]:
    from .. import generators

    attrs: dict[str, t.Any] = {
        "__doc__": """Generate new code.""",
    }

    for name in ("controller", "model"):
        attrs[name] = _get_cmd(app, generators, f"gen_{name}")

    return type("Generators", (Cli,), attrs)


def get_install_cl(app: "App") -> t.Type[Cli]:
    from .. import auth, i18n

    attrs: dict[str, t.Any] = {
        "__doc__": "",
        "auth": _get_cmd(app, auth, "install"),
        "i18n": _get_cmd(app, i18n, "install"),
        # "storage": _get_cmd(app, storage, "install"),
        # "text": _get_cmd(app, text, "install"),
    }
    return type("Install", (Cli,), attrs)


def _get_cmd(app, module: t.Any, name: str) -> t.Callable:
    func = getattr(module, name)
    @wraps(func)
    def cmd(_, *args, **kw):
        return func(app, *args, **kw)

    return cmd
