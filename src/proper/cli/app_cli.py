import importlib
import multiprocessing
import os
import sys
import typing as t
from functools import wraps

import peewee as pw
from proper_cli import Cli

from ..check import ERROR, run_checks
from ..check.gil import free_threaded as _free_threaded
from ..check.gil import gil_enabled as _gil_enabled
from ..models.migrations import pending_migrations
from .db_cli import get_db_cli
from .jx_cli import get_jx_cli


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from bearings import Server

    from ..app import App
    from ..channels.cable import Cable


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
        "check": get_check_cmd(app),
        "db": get_db_cli(app),
        "g": get_generators_cli(app),
        "install": get_install_cli(app),
        "jx": get_jx_cli(app),
    }

    return t.cast(type[Cli], type("appCL", (Cli,), attrs))


def _check_free_threading(config) -> None:
    """Proper serves on free-threaded Python: one process, workers as
    threads, one copy of everything. Refuse the GIL unless `ALLOW_GIL`."""
    if not _gil_enabled():
        return
    if config.ALLOW_GIL:
        print(
            "[WARNING] Serving with the GIL: more memory, less parallelism. "
            "Use a free-threaded Python (`uv python install 3.14t`).",
            flush=True,
        )
        return
    if _free_threaded():
        why = (
            "This is a free-threaded Python, but an extension module turned the "
            "GIL back on when it was imported; Python named it in a "
            "RuntimeWarning above. Upgrade or replace that module."
        )
    else:
        why = (
            "This Python has the GIL. Proper serves on free-threaded Python: "
            "install one with `uv python install 3.14t` and run the app with it."
        )
    print(
        f"[ERROR] {why}\nTo serve with the GIL anyway, set ALLOW_GIL = True "
        "in the config.",
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(1)


def _warn_of_pending_migrations(app: "App") -> None:
    """Say which databases have migrations that were not applied."""
    try:
        pending = pending_migrations(app)
    except pw.PeeweeException as err:
        print(f"[WARNING] Could not check the migrations: {err}", flush=True)
        return
    for name, migrations in pending.items():
        print(
            f"[WARNING] The database '{name}' has {len(migrations)} migration(s) "
            f"not applied ({', '.join(migrations)}). Run `proper db migrate`.",
            flush=True,
        )


def _serve(
    *,
    target: str,
    address: str,
    port: int,
    workers: int,
    threads: int,
    debug: bool,
) -> None:
    """Start Bearings and block until SIGINT or SIGTERM.

    `workers` are Bearings' event loops, which do the network I/O and never
    run Python; `threads` are its worker pool, which runs the app.

    A Proper app is served with Bearings' raw interface (`App._bearings`),
    which builds the request from the head Bearings parsed; anything else,
    as a WSGI app.

    A plain function, with plain arguments, so it can run in a fresh
    process: the reloader's, or one of `PROCESSES`.
    """
    from bearings import serve

    def started(server: "Server") -> None:
        print(
            f"[INFO] Listening on {address}:{server.port} "
            f"({workers} workers, {threads} threads, pid {os.getpid()})",
            flush=True,
        )

    app = _load_app(target)
    raw_app = getattr(app, "_bearings", None)
    serve(
        raw_app or app,
        raw=raw_app is not None,
        host=address,
        port=port,
        loops=workers,
        workers=threads,
        access_log="combined" if debug else None,
        started=started,
    )


def _load_app(target: str) -> "App":
    """The app a server target (`"module:attribute"`) names. In the process
    that serves it, the same object the server gets."""
    module, _, attr = target.partition(":")
    return getattr(importlib.import_module(module), attr or "app")


def _serve_group(
    web: dict,
    processes: int = 1,
    *,
    start_cable: bool = False,
    serve: "Callable" = _serve,
) -> list[multiprocessing.Process]:
    """Run the web server here, plus `processes - 1` more copies of it in
    child processes, all on the same port. Take the children down when this
    server stops, and return them, once they have.

    The extra processes are for machines with many cores: threads of one
    interpreter contend for its shared objects, and two smaller groups of
    them do better than one big one.

    With `start_cable`, the app's cable (`Cable`) serves the WebSockets
    from this process only: the other processes forward their broadcasts
    to it.
    """
    owner = _load_app(web["target"]) if start_cable else None
    cable = t.cast("Cable", owner.cable) if owner is not None else None
    if cable is not None:
        cable.start_server()
    ctx = multiprocessing.get_context("spawn")
    children = []
    for n in range(2, processes + 1):
        children.append(ctx.Process(target=serve, kwargs=web, name=f"proper-web-{n}", daemon=True))
    for child in children:
        child.start()
    try:
        serve(**web)
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
        for child in children:
            child.join(timeout=10)
        if cable is not None:
            cable.stop_server()
    return children


def _log_changes(changes: set) -> None:
    # Printed rather than logged: the `proper` logger has no handler of its
    # own, and this must show up next to the server's lines.
    files = ", ".join(sorted(path for _change, path in changes))
    print(f"[INFO] Changes detected, restarting the server: {files}", flush=True)


def _serve_restarting_on_changes(
    path: str, target: "Callable", kwargs: dict
) -> None:
    """Run `target(**kwargs)` in a child process, and start a new one
    whenever a file under `path` changes.

    Bearings has no reloader of its own, and restarting the whole group
    from outside also covers the other servers of the group.
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
                How many workers (threads with their own event loop) to
                start in each process.

        The app is loaded from `config.APP_TARGET`, or from `app` in the
        module that created it when that is empty. Bearings serves it over
        WSGI. A cable that serves WebSockets (`Cable`) starts in this
        process, on `CABLE_PORT`. `config.PROCESSES` starts that many
        copies of the web server.
        """
        from ..helpers import show_banner, show_welcome

        config = app.config
        _check_free_threading(config)
        _warn_of_pending_migrations(app)
        reload = config.DEBUG if config.RELOAD is None else bool(config.RELOAD)
        workers = int(workers or config.WORKERS or 1)
        web = {
            "target": config.APP_TARGET or f"{app.import_name}:app",
            "address": host,
            "port": int(port or config["PORT"] or 2300),
            "workers": workers,
            "threads": app.max_threads,
            "debug": bool(config.DEBUG),
        }
        group: dict[str, t.Any] = {
            "web": web,
            "processes": max(1, int(config.PROCESSES or 1)),
            "start_cable": bool(getattr(app.cable, "serves_websockets", False)),
        }

        if config.DEBUG:
            show_banner()
            show_welcome(config["HOST"])
        # Fail here, before any request, if a controller can never dispatch.
        app.lower()
        if reload:
            _serve_restarting_on_changes(str(app.root_path), _serve_group, group)
        else:
            _serve_group(**group)

    return run


def get_check_cmd(app: "App") -> t.Callable:
    def check(self):
        """Find the mistakes of the app before it runs.

        Checks the config, the storage and mailers, the controllers and
        routes, the views, the models and their migrations, the seeds, the
        forms, the emails and the locales. Prints each problem as
        `path:line: error|warning: message`. Exits with 1 when there is an
        error; warnings alone exit with 0.

        Run it from the root of the project: the migrations and seeds are
        read from `db/` there.
        """
        problems = run_checks(app)
        for problem in problems:
            print(problem)
        errors = sum(problem.level == ERROR for problem in problems)
        warnings = len(problems) - errors
        if not problems:
            print("No problems found.")
        else:
            print(f"{errors} error(s), {warnings} warning(s)")
        if errors:
            raise SystemExit(1)

    return check


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
                # The class the request runs on: the route's controller (an
                # inherited action routed by `resource()`) or the class that
                # defines `to`.
                qualname = route.to.__qualname__
                mod = route.to.__module__
                if route.controller is not None:
                    action = qualname.rsplit(".", 1)[-1]
                    qualname = f"{route.controller.__qualname__}.{action}"
                    mod = route.controller.__module__
                prefix = ""
                if ".controllers." in mod:
                    parts = mod.split(".controllers.", 1)[1]
                    segments = parts.split(".")
                    if len(segments) > 1:
                        prefix = "/".join(segments[:-1]) + "/"
                to = prefix + qualname
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
