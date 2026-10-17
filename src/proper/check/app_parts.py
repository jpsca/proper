import difflib
import re
import typing as t

from formidable import Form

from ..core.config import default_config
from ..emails import EmailMessage
from ..helpers.imports import get_class
from ..storage.attachment import _service_types
from ..tools import auth, cable, cache, db, mailer, queue, storage
from ..tools import i18n as i18n_tool
from .problem import (
    ERROR,
    WARNING,
    Problem,
    of_app,
    relpath,
    subclasses,
    where,
    where_attr,
)


if t.TYPE_CHECKING:
    from ..app import App


__all__ = (
    "check_config",
    "check_emails",
    "check_forms",
    "check_locales",
    "check_services",
    "known_settings",
)

# Settings read by the framework that have no default in the config
UNDECLARED_SETTINGS = {
    "RICH_TEXT_ALLOWED_ATTRIBUTES",
    "RICH_TEXT_ALLOWED_STYLES",
    "RICH_TEXT_ALLOWED_TAGS",
    "RICH_TEXT_ALLOWED_URL_SCHEMES",
    "RICH_TEXT_SANITIZE",
    "TRUSTED_ORIGINS",
}
# How alike an unknown setting must be to a known one to be called a typo
TYPO_CUTOFF = 0.85
# Missing keys shown per locale
SHOW_KEYS = 5


def check_forms(app: "App") -> list[Problem]:
    """Each field of a form with `orm_cls` is an attribute of that model:
    `save()` sets every field on the object, and Peewee keeps a value of a
    name that isn't a field without storing it."""
    problems = []
    for form in subclasses(Form):
        if not of_app(app, form):
            continue
        model = getattr(form._ProcessedMeta, "orm_cls", None)
        if model is None:
            continue
        for name in form._field_names:
            if not hasattr(model, name):
                problems.append(Problem(
                    ERROR,
                    f"`{form.__name__}.{name}` is not a field of {model.__name__}: "
                    f"`save()` would drop its value",
                    **where_attr(form, name),
                ))
    return problems


def check_emails(app: "App") -> list[Problem]:
    """Each email without a `body` has one of its templates. A class with
    subclasses, or named `Base...`, is taken to be a base for others."""
    problems = []
    for email in subclasses(EmailMessage):
        if not of_app(app, email) or email.body:
            continue
        if email.__name__.startswith("Base") or email.__subclasses__():
            continue
        name = email.__module__.split(".")[-1].removesuffix("_email")
        html = app.views_path / "emails" / f"{name}.jx"
        text = app.views_path / "emails" / f"{name}.txt.jx"
        if not html.exists() and not text.exists():
            problems.append(Problem(
                ERROR,
                f"{email.__name__} has no body and no template: "
                f"write {relpath(html)} or {relpath(text)}",
                **where(email),
            ))
    return problems


def known_settings() -> set[str]:
    """The names of the settings the framework reads."""
    known = set(default_config) | UNDECLARED_SETTINGS
    for tool in (auth, cable, cache, db, i18n_tool, mailer, queue, storage):
        name = getattr(tool, "NAME", None)
        if name:
            known.add(name)
        else:
            known |= set(tool.DEFAULT_CONFIG)
    return known


def check_config(app: "App") -> list[Problem]:
    """An unknown setting that looks like a known one is probably a typo:
    the known one keeps its default. A setting of the app's own, unlike any
    known one, is fine."""
    problems = []
    known = known_settings()
    for key in app.config:
        if key in known:
            continue
        match = difflib.get_close_matches(key, known, n=1, cutoff=TYPO_CUTOFF)
        if match:
            problems.append(Problem(
                WARNING,
                f"unknown setting `{key}`: did you mean `{match[0]}`?",
                **_where_setting(app, key),
            ))
    return problems


def _where_setting(app: "App", key: str) -> dict[str, t.Any]:
    """Where a file of the app's config folder sets `key`."""
    rx = re.compile(rf"^{re.escape(key)}\s*[:=]")
    if not app.config_path.is_dir():
        return {}
    for path in sorted(app.config_path.rglob("*.py")):
        for number, text in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if rx.match(text):
                return {"path": relpath(path), "line": number}
    return {}


def check_services(app: "App") -> list[Problem]:
    """The storage and mailers of the config can be loaded: today they
    fail on their first use."""
    problems = []
    config = app.config
    storages = config.get("STORAGES") or {}
    default = config.get("STORAGE")
    if default and default not in storages:
        problems.append(Problem(
            ERROR,
            f"STORAGE is `{default}`, which is not in STORAGES "
            f"({', '.join(storages) or 'empty'})",
            **_where_setting(app, "STORAGE"),
        ))
    types = _service_types()
    for name, options in storages.items():
        kind = (options or {}).get("type", "")
        if kind not in types:
            problems.append(Problem(
                ERROR,
                f"STORAGES[{name!r}] has the type `{kind}`, which is not a "
                f"storage service (there are: {', '.join(sorted(types))}); "
                f"a service of the app must be imported when it starts",
                **_where_setting(app, "STORAGES"),
            ))
    for name, options in (config.get("MAILERS") or {}).items():
        kind = (options or {}).get("type", "")
        try:
            get_class(kind)
        except (ImportError, AttributeError, ValueError) as err:
            problems.append(Problem(
                ERROR,
                f"MAILERS[{name!r}] has the type `{kind}`, which can't be "
                f"imported ({type(err).__name__}: {err})",
                **_where_setting(app, "MAILERS"),
            ))
    return problems


def check_locales(app: "App") -> list[Problem]:
    """Every locale has the keys of the others: a missing one shows as
    `<missing:key/>`."""
    i18n = getattr(app, "i18n", None)
    if i18n is None:
        return []
    problems = []
    missing = i18n.test_for_incomplete_locales()
    for locale, keys in sorted(missing.items()):
        names = sorted(keys)
        shown = ", ".join(names[:SHOW_KEYS])
        if len(names) > SHOW_KEYS:
            shown += f" and {len(names) - SHOW_KEYS} more"
        problems.append(Problem(
            WARNING,
            f"the locale `{locale}` lacks {len(names)} key(s) that another has: {shown}",
            path=relpath(app.locales_path),
        ))
    return problems
