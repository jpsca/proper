import logging
import re
import typing as t
from importlib import import_module
from pathlib import Path

import peewee as pw
from peewee_migrate import Migrator, Router
from peewee_migrate.router import compile_migrations, load_models

from ..models.seeds import _iter_seed_modules, _resolve_package
from .problem import ERROR, WARNING, Problem, relpath, where, where_attr


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("app_models", "check_migrations", "check_models", "check_seeds")

# The router logs a migration that fails to load; here it is reported
_SILENT = logging.getLogger("proper.check.migrations")
_SILENT.disabled = True

RX_PREFIX = re.compile(r"^(\d{3})_")


def app_models(app: "App") -> list[type[pw.Model]]:
    """The models that `models/__init__.py` of the app imports: the ones
    the migrations are made from."""
    name = f"{app.name}.models"
    try:
        module = import_module(name)
    except ModuleNotFoundError as err:
        if err.name == name:
            return []
        raise
    return sorted(load_models(module), key=lambda model: model.__name__)


def check_models(app: "App") -> list[Problem]:
    """No field hides a method of the model, every foreign key points to a
    model of its database that the migrations make, and no two models of a
    database have the same table."""
    problems = []
    tables: dict[tuple[int, str], type] = {}
    models = app_models(app)
    for model in models:
        for name, field in model._meta.fields.items():
            message = _foreign_key_problem(app, model, field, models)
            if message:
                problems.append(Problem(ERROR, message, **where_attr(model, name)))
            hidden = _hidden_by_field(model, name)
            if hidden:
                problems.append(Problem(
                    ERROR,
                    f"the field `{model.__name__}.{name}` hides the method "
                    f"`{name}` of {hidden.__name__}; rename the field and "
                    f'keep its column with `column_name="{name}"`',
                    **where_attr(model, name),
                ))
        key = (id(model._meta.database), model._meta.table_name)
        first = tables.setdefault(key, model)
        if first is not model:
            problems.append(Problem(
                ERROR,
                f"{model.__name__} uses the table `{model._meta.table_name}` "
                f"of {first.__name__}",
                **where(model),
            ))
    return problems


def _foreign_key_problem(
    app: "App",
    model: type[pw.Model],
    field: pw.Field,
    models: list[type[pw.Model]],
) -> str:
    """What is wrong with a foreign key, or `""`: a `DeferredForeignKey` to
    a model that was never declared, a model that `models/__init__.py`
    doesn't import (the migrations don't make its table), or one of
    another database (it can't be joined, nor the key enforced)."""
    label = f"`{model.__name__}.{field.name}`"
    if isinstance(field, pw.DeferredForeignKey):
        return (
            f"{label} is a `DeferredForeignKey` to `{field.rel_model_name}`, "
            f"and no model of that name was declared"
        )
    if not isinstance(field, pw.ForeignKeyField):
        return ""
    target = field.rel_model
    if target is model:
        return ""
    if target not in models:
        return (
            f"{label} points to {target.__name__}, which `models/__init__.py` "
            f"doesn't import: the migrations don't make its table"
        )
    if target._meta.database is not model._meta.database:
        names = {id(db): name for name, db in app.db.items()}
        return (
            f"{label} points to {target.__name__}, of another database "
            f"(`{names.get(id(target._meta.database), '?')}`, not "
            f"`{names.get(id(model._meta.database), '?')}`): it can't be joined, "
            f"nor the key enforced"
        )
    return ""


def _hidden_by_field(model: type, name: str) -> type | None:
    """The class whose method the field `name` hides, if any."""
    for klass in model.__mro__[1:]:
        attr = klass.__dict__.get(name)
        if attr is None:
            continue
        if isinstance(attr, pw.FieldAccessor):
            return None
        # A field may stand in for a property, as for a default value
        if callable(attr) or isinstance(attr, (classmethod, staticmethod)):
            return klass
        return None
    return None


def check_migrations(app: "App") -> list[Problem]:
    """The files of `db/<database>/` are migrations, and the models are what
    those migrations make (read without the database)."""
    problems = []
    models = app_models(app)
    for name in app.config.DATABASES:
        db = app.db[name]
        folder = Path("db", name)
        names = []
        if folder.is_dir():
            names, found = _migration_files(folder)
            problems.extend(found)
        db_models = [model for model in models if model._meta.database is db]
        if db_models:
            problems.extend(_compare(name, db, folder, names, db_models))
    return problems


def _migration_files(folder: Path) -> tuple[list[str], list[Problem]]:
    """The names of the migrations in `folder`, and the problems with its
    files: one that isn't read, or two with the same number."""
    problems = []
    names = []
    numbers: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if path.suffix != ".py" or path.name == "__init__.py":
            continue
        if not Router.filemask.match(path.name):
            problems.append(Problem(
                WARNING,
                "this file is not run as a migration: the name of one is "
                "three digits, `_` and a name, like `004_add_tags.py`",
                path=relpath(path),
            ))
            continue
        names.append(path.stem)
        match = RX_PREFIX.match(path.name)
        assert match
        number = match[1]
        if number in numbers:
            problems.append(Problem(
                WARNING,
                f"two migrations are number {number}: this one and "
                f"{numbers[number]}.py (from two branches?); they run in "
                f"the order of their names",
                path=relpath(path),
            ))
        else:
            numbers[number] = path.stem
    return names, problems


def _compare(
    name: str,
    db: pw.Database,
    folder: Path,
    names: list[str],
    models: list[type[pw.Model]],
) -> list[Problem]:
    router = Router(db, migrate_dir=folder, logger=_SILENT)
    migrator = Migrator(db)
    for migration in names:
        try:
            router.run_one(migration, migrator, fake=True)
        except Exception as err:
            return [Problem(
                ERROR,
                f"this migration can't be read ({type(err).__name__}: {err}), "
                f"so the models of `{name}` were not compared with the migrations",
                path=relpath(folder / f"{migration}.py"),
            )]
    code = compile_migrations(migrator, models)
    if not code:
        return []
    option = "" if name == "main" else f" --db {name}"
    return [Problem(
        ERROR,
        f"the models are not what the migrations of `{name}` make "
        f"({'; '.join(_operations(code))}): run `proper db create{option}`",
        path=relpath(folder),
    )]


def _operations(code: str) -> list[str]:
    """A short description of each change in the code of a migration."""
    operations = []
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line.startswith("@migrator.create_model"):
            following = lines[i + 1] if i + 1 < len(lines) else ""
            match = re.match(r"class (\w+)", following)
            operations.append(f"create the table of {match[1] if match else 'a model'}")
        elif line.startswith("migrator."):
            operations.append(line if len(line) <= 100 else line[:97] + "...")
    return operations


def check_seeds(app: "App") -> list[Problem]:
    """Each seed of `db/seeds/` runs somewhere: it has `envs` (a tuple) and
    `seed()`, and `__init__.py` imports it."""
    problems = []
    for name in app.config.DATABASES:
        package_name = _resolve_package(name)
        if package_name is None:
            continue
        folder = Path(*package_name.split("."))
        try:
            package = import_module(package_name)
        except Exception as err:
            problems.append(Problem(
                ERROR,
                f"the seeds can't be imported ({type(err).__name__}: {err})",
                path=relpath(folder / "__init__.py"),
            ))
            continue
        modules = [module for _, module in _iter_seed_modules(package)]
        imported = {module.__name__.rsplit(".", 1)[-1] for module in modules}
        for module in modules:
            loc: dict[str, t.Any] = {"path": relpath(module.__file__)} if module.__file__ else {}
            envs = getattr(module, "envs", None)
            if envs is None:
                problems.append(Problem(
                    WARNING,
                    'this seed has no `envs`, so it never runs; for example: `envs = ("dev",)`',
                    **loc,
                ))
            elif isinstance(envs, str):
                problems.append(Problem(
                    WARNING,
                    f"`envs` is a string, so it runs where APP_ENV is any part of "
                    f"{envs!r}; make it a tuple: `envs = ({envs!r},)`",
                    **loc,
                ))
            if not callable(getattr(module, "seed", None)):
                problems.append(Problem(ERROR, "this seed has no `seed()` function", **loc))
        for path in sorted(folder.glob("*.py")):
            if path.stem != "__init__" and path.stem not in imported:
                problems.append(Problem(
                    WARNING,
                    f"this seed never runs: `{relpath(folder / '__init__.py')}` doesn't import it",
                    path=relpath(path),
                ))
    return problems
