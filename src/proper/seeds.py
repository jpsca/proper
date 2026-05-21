"""Seed-data runner.

Seeds are small idempotent scripts that put canonical data into a database
(default roles, reference data, the first admin user). They live under
``db/seeds/`` and are registered as submodule imports in
``db/seeds/__init__.py`` (or, for a non-default database,
``db/seeds/<db_name>/__init__.py``).

Each seed module exposes:

- ``envs``: a tuple of ``APP_ENV`` values where the seed should run.
- ``seed()``: the entry point - takes no arguments, returns nothing.

The runner imports the seeds package, then iterates over its submodules in
import order (the ``__init__.py`` import order *is* the dependency graph).
For each submodule, the runner checks whether the current ``APP_ENV`` is in
``envs``; if so, it calls ``seed()``, otherwise it reports the seed as
skipped.

There is intentionally no ``--force`` flag: ``envs`` is the absolute
environment boundary.
"""
import os
import sys
import types
from importlib import import_module


__all__ = ["run_seeds"]


DEFAULT_DB = "main"


def run_seeds(name: str = "", db: str = DEFAULT_DB) -> bool:
    """Run seeds for ``db``, optionally filtering to a single seed by ``name``.

    Returns ``True`` if any seed ran or was skipped (i.e. seeds existed),
    ``False`` if no seeds package was found.
    """
    package_name = _resolve_package(db)
    if package_name is None:
        print(f"No seeds defined for '{db}'.")
        return False

    package = import_module(package_name)
    seeds = list(_iter_seed_modules(package))

    if name:
        seeds = [(n, mod) for n, mod in seeds if n == name]
        if not seeds:
            print(f"Seed '{name}' not found in {package_name.replace('.', '/')}/.")
            return False

    if not seeds:
        print(f"No seeds registered in {package_name.replace('.', '/')}/__init__.py.")
        return True

    app_env = os.getenv("APP_ENV", "dev")
    for seed_name, mod in seeds:
        envs = getattr(mod, "envs", ())
        path = f"{package_name.replace('.', '/')}/{seed_name}.py"
        if app_env in envs:
            mod.seed()
            print(f"{path} - ran")
        else:
            print(f"{path} - skipped (envs={envs!r}, APP_ENV={app_env!r})")
    return True


def _resolve_package(db: str) -> str | None:
    """Return the dotted package name to import, or ``None`` if missing.

    Resolution order:

    1. ``db/seeds/<db>/__init__.py`` - the per-database layout.
    2. ``db/seeds/__init__.py`` - the flat single-database layout (only
       used when ``db == "main"``).
    """
    if "db" not in sys.path and "" not in sys.path:
        sys.path.insert(0, "")

    if _has_init(("db", "seeds", db)):
        return f"db.seeds.{db}"
    if db == DEFAULT_DB and _has_init(("db", "seeds")):
        return "db.seeds"
    return None


def _has_init(parts: tuple[str, ...]) -> bool:
    from pathlib import Path
    return Path(*parts, "__init__.py").exists()


def _iter_seed_modules(package: types.ModuleType):
    """Yield ``(short_name, submodule)`` pairs in ``__init__.py`` import order.

    Only attributes of the package that are ``ModuleType`` *and* belong to
    the package itself are returned. Plain values, helper functions, and
    re-exports from elsewhere are filtered out.
    """
    prefix = package.__name__ + "."
    for attr_name, value in vars(package).items():
        if attr_name.startswith("_"):
            continue
        if not isinstance(value, types.ModuleType):
            continue
        if not value.__name__.startswith(prefix):
            continue
        yield attr_name, value
