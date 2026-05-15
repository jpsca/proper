import typing as t
from pathlib import Path

import inflection
from hecto import COLORS, printf


if t.TYPE_CHECKING:
    from ..app import App


SEED_TEMPLATE = '''\
# from {app_name}.models import ...


# APP_ENV values where this seed should run.
envs = ("dev", "test", "prod")


def seed():
    """{name_snake}"""
'''


def gen_seed(app: "App", name: str, db: str = "main") -> None:
    """Stub a new seed file under db/seeds/.

    Arguments:
        name:
            The seed name. Will be `snake_case`d for the filename.
        db ["main"]:
            Target database. Single-database apps use the flat layout
            (`db/seeds/`); pass `--db <name>` for any other database to use
            the per-database layout (`db/seeds/<name>/`).

    The generator creates `db/seeds/<name>.py` (or
    `db/seeds/<db>/<name>.py`) with a `seed()` skeleton, an `envs` tuple
    defaulting to all environments, and an import line in the
    corresponding `__init__.py`.
    """
    name_snake = inflection.underscore(name)
    seeds_dir = _seeds_dir(app, db)

    seeds_dir.mkdir(parents=True, exist_ok=True)
    init_path = seeds_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("")
        printf("create", str(init_path), color=COLORS.OK)

    seed_path = seeds_dir / f"{name_snake}.py"
    if seed_path.exists():
        printf("skip", str(seed_path), color=COLORS.WARNING)
    else:
        seed_path.write_text(
            SEED_TEMPLATE.format(app_name=app.name, name_snake=name_snake)
        )
        printf("create", str(seed_path), color=COLORS.OK)

    _register_in_init(init_path, name_snake)


def _seeds_dir(app: "App", db: str) -> Path:
    """Pick the directory for the new seed file.

    - "main" (the default db) uses the flat `db/seeds/` layout.
    - Any other db uses `db/seeds/<db>/`.
    """
    base = app.root_path.parent / "db" / "seeds"
    if db == "main":
        return base
    return base / db


def _register_in_init(init_path: Path, name_snake: str) -> None:
    """Append `from . import <name>  # noqa` to __init__.py if missing."""
    line = f"from . import {name_snake}  # noqa"
    text = init_path.read_text()
    if line in text.splitlines():
        return
    if text and not text.endswith("\n"):
        text += "\n"
    init_path.write_text(text + line + "\n")
    printf("update", str(init_path), color=COLORS.OK)
