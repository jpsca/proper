"""Decisions that cannot change between requests, taken once.

A request to `PostsController.show` needs to know which `before` and
`after` callbacks apply to `show`, and which template to render when the
action renders nothing itself. None of that depends on the request, so it
is computed once per `(controller, action)` and kept in a `DispatchPlan`.

`lower(app)` builds the plan of every routed action up front and validates
it. `Controller` builds any plan still missing the first time it needs it,
with the same code, so there is one path, not a fast one and a slow one.
"""
import logging
import typing as t
from dataclasses import dataclass, field

from ..controller.template_resolver import find_template
from ..helpers import logger, make_list
from ..helpers.imports import import_string


if t.TYPE_CHECKING:
    from ..app import App


class LoweringError(Exception):
    """A controller declares something that can never work, like a callback
    that names a method it does not have."""


@dataclass(slots=True)
class DispatchPlan:
    """Everything `Controller._dispatch` needs for one action of one class.

    `before` and `after` hold `(attribute name, is_method)` pairs, in the
    order they run. `is_method` is `True` when the attribute is a plain
    function on the class, so the bound method is the callback; otherwise
    the attribute is read and every callable it yields is called (a property
    returning a list of callbacks, for example).
    """

    cls: type
    action: str
    before: tuple[tuple[str, bool], ...]
    after: tuple[tuple[str, bool], ...]
    prefixes: tuple[str, ...]
    #: Whether to log each callback. Frozen at build time, so the request
    #: path never asks the logger.
    log: bool
    #: Resolved template name by the formats the client accepts. Filled on
    #: first use, bounded, and skipped while the catalog reloads templates.
    views: dict[tuple[str, ...], str] = field(default_factory=dict)


# Plans by `(controller class, action name)`. Classes are defined at import
# time and templates only change in debug mode, where the views memo is
# off, so there is nothing to invalidate.
_PLANS: dict[tuple[type, str], DispatchPlan] = {}

# How many `accept` combinations one plan remembers a template for. Any
# real client sends a handful; the cap is for the ones that make them up.
MAX_VIEWS_PER_PLAN = 64


def callback_applies(options: dict[str, t.Any], action: str | None) -> bool:
    """Whether a callback with these `only`/`exclude` options runs for `action`."""
    if not options:
        return True
    only = options.get("only", None)
    exclude = options.get("exclude", None)
    if only and action not in make_list(only):
        return False
    if exclude and action in make_list(exclude):
        return False
    return True


def class_callbacks(cls: type) -> "tuple[list[dict], list[dict]]":
    """The `before` and `after` callbacks declared by `cls` and its
    ancestors, flattened: `before` from the base class down, `after` from
    `cls` up, as the request runs them."""
    mro = cls.mro()
    before = [
        cb
        for klass in reversed(mro)
        for cb in make_list(klass.__dict__.get("before") or [])
    ]
    after = [
        cb
        for klass in mro
        for cb in make_list(klass.__dict__.get("after") or [])
    ]
    return before, after


def view_prefixes(cls: type) -> tuple[str, ...]:
    """View-folder prefixes to search for `cls`, walking up its MRO.

    Subclass first, then each ancestor controller, stopping before
    `Controller` itself. Gives `application/` fallbacks and similar
    without any explicit config.
    """
    from ..controller.controller import Controller

    prefixes: list[str] = []
    for klass in cls.mro():
        if klass is Controller or klass is object:
            break
        module = getattr(klass, "__module__", "")
        if not module or module.startswith("proper."):
            continue
        prefix = module.split(".", 2)[-1]
        prefix = prefix.removesuffix("_controller")
        prefix = prefix.replace(".", "/")
        if prefix not in prefixes:
            prefixes.append(prefix)
    return tuple(prefixes)


def _lower_callbacks(
    cls: type, callbacks: list[dict], action: str
) -> tuple[tuple[str, bool], ...]:
    lowered = []
    for cb in callbacks:
        if not callback_applies(cb, action):
            continue
        name = cb["do"]
        attr = getattr(cls, name, None)
        # A function on the class binds to the instance: one call. Anything
        # else (a property, a descriptor) is read per request and can yield
        # several callbacks.
        lowered.append((name, callable(attr) and not isinstance(attr, type)))
    return tuple(lowered)


def lower_dispatch(cls: type, action: str) -> DispatchPlan:
    """Build the plan for `action` of `cls`. Pure: no memo, no validation."""
    before, after = class_callbacks(cls)
    return DispatchPlan(
        cls=cls,
        action=action,
        before=_lower_callbacks(cls, before, action),
        after=_lower_callbacks(cls, after, action),
        prefixes=view_prefixes(cls),
        log=logger.isEnabledFor(logging.DEBUG),
    )


def plan_for(cls: type, action: str) -> DispatchPlan:
    """The plan for `action` of `cls`, built on the first call."""
    key = (cls, action)
    plan = _PLANS.get(key)
    if plan is None:
        plan = _PLANS[key] = lower_dispatch(cls, action)
    return plan


def validate(plan: DispatchPlan) -> None:
    """Raise `LoweringError` if a callback of the plan names a missing attribute."""
    for kind, callbacks in (("before", plan.before), ("after", plan.after)):
        for name, _ in callbacks:
            if not hasattr(plan.cls, name):
                raise LoweringError(
                    f"{plan.cls.__name__}: `{kind}` callback `{name}`"
                    f" is not a method of the controller"
                )


def resolve_view(
    plan: DispatchPlan,
    catalog: t.Any,
    formats: tuple[str, ...],
    *,
    cache: bool = True,
) -> str:
    """The template to render for the plan's action when the client accepts
    `formats`, remembered per `formats` unless `cache` is off."""
    name = plan.views.get(formats)
    if name is None:
        name = find_template(
            catalog,
            plan.prefixes,
            plan.action,
            formats,
            controller=plan.cls.__name__,
        )
        if cache and len(plan.views) < MAX_VIEWS_PER_PLAN:
            plan.views[formats] = name
    return name


def _routed_actions(app: "App") -> "t.Iterator[tuple[type, str]]":
    for route in app.routes:
        if route.to is not None:
            yield route.resolve()
    for handler in app.router.error_handlers.values():
        cls_name, action = handler.__qualname__.rsplit(".", 1)
        module = import_string(handler.__module__)
        yield getattr(module, cls_name), action


def lower(app: "App") -> list[DispatchPlan]:
    """Build and validate the plan of every routed action and error handler
    of `app`. Raises `LoweringError` on the first invalid one."""
    plans = []
    seen: set[tuple[type, str]] = set()
    for cls, action in _routed_actions(app):
        if (cls, action) in seen:
            continue
        seen.add((cls, action))
        plan = plan_for(cls, action)
        validate(plan)
        plans.append(plan)
    return plans


def reset() -> None:
    """Forget every plan. For tests."""
    _PLANS.clear()
