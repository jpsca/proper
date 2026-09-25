import multiprocessing
import sysconfig
import typing as t
from functools import wraps

from proper_cli import Cli

from .db_cli import get_db_cli


if t.TYPE_CHECKING:
    from collections.abc import Callable

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


def _free_threaded() -> bool:
    """Whether this Python was built without the GIL (a "3.14t" build)."""
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def _blocking_threads(max_threads: int, workers: int) -> int:
    """Threads per worker for the WSGI server, out of the app's
    `MAX_THREADS`, which is per process. Free-threaded workers share the
    process, so they share that budget; process workers each get all of it.

    Granian's own default is in the hundreds, which floods a database with
    connections and buys nothing for CPU-bound Python.
    """
    if _free_threaded():
        return max(1, -(-max_threads // workers))
    return max(1, max_threads)


def _serve(
    *,
    target: str,
    interface: str,
    address: str,
    port: int,
    workers: int,
    blocking_threads: int,
    reload: bool,
    debug: bool,
) -> None:
    """Start Granian and block until it stops.

    A plain function, with plain arguments, so the free-threaded reloader can
    run it in a fresh process.
    """
    from granian import Granian
    from granian.constants import Interfaces
    from granian.log import LogLevels

    Granian(
        target=target,
        interface=Interfaces(interface),
        address=address,
        port=port,
        workers=workers,
        blocking_threads=blocking_threads if interface == "wsgi" else None,
        websockets=interface == "rsgi",
        reload=reload,
        log_level=LogLevels.debug if debug else LogLevels.info,
        log_access=debug,
    ).serve()


def _serve_with_cable(
    web: dict, cable: dict, *, serve: "Callable" = _serve
) -> multiprocessing.Process:
    """Run the web server here and the WebSocket server in a child process,
    and take the child down when the web server stops. Returns the child,
    once it has.

    Two processes because they speak different interfaces: WSGI has no
    WebSockets, and RSGI pays for its event loop on every request.
    """
    child = multiprocessing.get_context("spawn").Process(
        target=serve, kwargs=cable, name="proper-cable", daemon=True
    )
    child.start()
    try:
        serve(**web)
    finally:
        if child.is_alive():
            child.terminate()
        child.join(timeout=10)
    return child


def _log_changes(changes: set) -> None:
    # Printed rather than logged: the `proper` logger has no handler of its
    # own, and this must show up next to Granian's lines.
    files = ", ".join(sorted(path for _change, path in changes))
    print(f"[INFO] Changes detected, restarting the server: {files}", flush=True)


def _serve_restarting_on_changes(
    path: str, target: "Callable", kwargs: dict
) -> None:
    """Run `target(**kwargs)` in a child process, and start a new one
    whenever a file under `path` changes.

    Granian's own reloader replaces its worker processes, which is not
    possible on free-threaded Python, where the workers are threads of a
    single process, nor covers a second server. Restarting the whole
    process from outside does both.
    """
    import watchfiles

    watchfiles.run_process(path, target=target, kwargs=kwargs, callback=_log_changes)


def get_run_cli(app: "App") -> t.Callable:
    def run(self, host="0.0.0.0", port=0, workers=0):
        """Run the server.

        Arguments:
            host ["0.0.0.0"]:
                The address to listen on.
            port [config PORT]:
                The port to listen on.
            workers [config WORKERS]:
                How many workers to start.

        The app is loaded from `config.APP_TARGET`, or from `app` in the
        module that created it when that is empty. `config.INTERFACE`
        picks WSGI (the default) or RSGI. With WSGI and a `CABLE_PORT`, a
        second process serves the WebSockets over RSGI on that port.
        """
        from ..helpers import show_banner, show_welcome

        config = app.config
        reload = config.DEBUG if config.RELOAD is None else bool(config.RELOAD)
        interface = str(config.INTERFACE or "wsgi").lower()
        if interface not in ("wsgi", "rsgi"):
            raise ValueError(f"INTERFACE must be 'wsgi' or 'rsgi', not {config.INTERFACE!r}")
        workers = int(workers or config.WORKERS or 1)
        options = {
            "target": config.APP_TARGET or f"{app.import_name}:app",
            "interface": interface,
            "address": host,
            "port": int(port or config["PORT"] or 2300),
            "workers": workers,
            "blocking_threads": _blocking_threads(app.max_threads, workers),
            "debug": bool(config.DEBUG),
        }
        cable_port = int(config.CABLE_PORT or 0)
        show_banner()
        show_welcome(config["HOST"])

        if cable_port and interface == "wsgi":
            # The WebSockets get their own RSGI process; Granian's reloader
            # would not restart it, so reloading is always done from outside.
            web = {**options, "reload": False}
            cable = {
                **options,
                "interface": "rsgi",
                "port": cable_port,
                "workers": 1,
                "reload": False,
            }
            if reload:
                _serve_restarting_on_changes(
                    str(app.root_path), _serve_with_cable, {"web": web, "cable": cable}
                )
            else:
                _serve_with_cable(web, cable)
        elif reload and _free_threaded():
            _serve_restarting_on_changes(
                str(app.root_path), _serve, {**options, "reload": False}
            )
        else:
            _serve(reload=reload, **options)

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

    for name in ("resource", "model", "controller", "email", "seed", "channel"):
        attrs[name] = _get_cmd(app, generators, f"gen_{name}")

    return t.cast(type[Cli], type("Generators", (Cli,), attrs))


def get_install_cli(app: "App") -> type[Cli]:
    from proper import auth, channels, i18n, rich_text, storage

    attrs: dict[str, t.Any] = {
        "__doc__": "",
        "auth": _get_cmd(app, auth, "install"),
        "i18n": _get_cmd(app, i18n, "install"),
        "storage": _get_cmd(app, storage, "install"),
        "channels": _get_cmd(app, channels, "install"),
        "rich_text": _get_cmd(app, rich_text, "install"),
    }
    return t.cast(type[Cli], type("Install", (Cli,), attrs))


def _get_cmd(app, module: t.Any, name: str) -> t.Callable:
    func = getattr(module, name)
    @wraps(func)
    def cmd(_, *args, **kw):
        return func(app, *args, **kw)

    return cmd
