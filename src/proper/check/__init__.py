"""`proper check`: find the mistakes of an app before it runs.

It imports the app, as every command does, and looks at what it built:
the routes, controllers, views, models and their migrations, seeds,
forms, emails, config and locales. Most of what it finds fails today
only when a request reaches it, or never fails and loses data.

Each check is a function of the app that returns the `Problem`s it
found; `run_checks` runs them all, in order.
"""
import typing as t

from .app_parts import (
    check_config,
    check_emails,
    check_forms,
    check_locales,
    check_services,
)
from .models import check_migrations, check_models, check_seeds
from .problem import ERROR, WARNING, Problem
from .routes import check_controllers, check_routes, check_views


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..app import App


__all__ = ("CHECKS", "ERROR", "WARNING", "Problem", "run_checks")

CHECKS: "tuple[Callable[[App], list[Problem]], ...]" = (
    check_config,
    check_services,
    check_controllers,
    check_routes,
    check_views,
    check_models,
    check_migrations,
    check_seeds,
    check_forms,
    check_emails,
    check_locales,
)


def run_checks(app: "App") -> list[Problem]:
    """Every problem that the checks find in `app`."""
    return [problem for check in CHECKS for problem in check(app)]
