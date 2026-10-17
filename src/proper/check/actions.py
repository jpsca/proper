import types
import typing as t

from ..helpers import make_list
from .problem import ERROR, WARNING, Problem, of_app, where_attr


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("check_action_names",)

# The options of a rate limit that may name a method of the controller
RATE_LIMIT_METHODS = ("to", "within", "by", "react_with")


def check_action_names(app: "App") -> list[Problem]:
    """The names of actions in `only`/`exclude` (of the `before`/`after`
    callbacks and of `rate_limit`) and in `skip_authentication` are actions
    of a controller, and the method names of `rate_limit` are methods.

    A list declared by a base class or a concern is checked against the
    actions of all the routed controllers based on it: a name that none of
    them has is a warning (a typo never matches, so it runs, or skips, for
    no action). A missing method is an error: it fails on the request."""
    routed = _routed_actions(app)
    declared: dict[type, set[str]] = {}
    for cls, actions in routed.items():
        for klass in cls.__mro__:
            if of_app(app, klass):
                declared.setdefault(klass, set()).update(actions)

    problems: dict[tuple, Problem] = {}
    for klass, actions in declared.items():
        bases = [cls for cls in routed if issubclass(cls, klass)]
        owner = klass.__name__ if bases == [klass] else f"any controller based on {klass.__name__}"
        for attr, label, names in _action_lists(klass):
            for name in names:
                if name not in actions:
                    problem = Problem(
                        WARNING,
                        f"{label} names `{name}`, which is not an action of {owner}",
                        **where_attr(klass, attr),
                    )
                    problems.setdefault((problem.path, problem.line, problem.message), problem)
        for option, method in _rate_limit_methods(klass):
            for cls in bases:
                if not callable(getattr(cls, method, None)):
                    problem = Problem(
                        ERROR,
                        f"`{option}` of `rate_limit` names `{method}`, which is not "
                        f"a method of {cls.__name__}",
                        **where_attr(klass, "rate_limit"),
                    )
                    problems.setdefault((problem.path, problem.line, problem.message), problem)
    return list(problems.values())


def _routed_actions(app: "App") -> dict[type, set[str]]:
    """The actions that the routes and error handlers reach, by controller.
    A route that can't be resolved is left to `check_controllers`."""
    routed: dict[type, set[str]] = {}
    for route in app.routes:
        if route.to is None:
            continue
        try:
            cls, action = route.resolve()
        except (ImportError, AttributeError):
            continue
        routed.setdefault(cls, set()).add(action)
    for handler in app.router.error_handlers.values():
        function = t.cast(types.FunctionType, handler)
        cls = _handler_class(function)
        if cls is not None:
            routed.setdefault(cls, set()).add(function.__name__)
    return routed


def _handler_class(handler: types.FunctionType) -> type | None:
    """The class of a method, from its globals: its `__qualname__` names it."""
    cls_name, _, _ = handler.__qualname__.rpartition(".")
    cls = handler.__globals__.get(cls_name)
    return cls if isinstance(cls, type) else None


def _action_lists(klass: type) -> t.Iterator[tuple[str, str, list[str]]]:
    """The lists of action names that `klass` itself declares: the attribute,
    a description, and the names."""
    attrs = vars(klass)
    for kind in ("before", "after"):
        for callback in make_list(attrs.get(kind) or []):
            if not isinstance(callback, dict):
                continue
            for option in ("only", "exclude"):
                if callback.get(option):
                    yield kind, (
                        f"`{option}` of the `{kind}` callback `{callback.get('do')}`"
                    ), make_list(callback[option])
    skip = attrs.get("skip_authentication")
    if skip and not isinstance(skip, bool):
        yield "skip_authentication", "`skip_authentication`", make_list(skip)
    for limit in make_list(attrs.get("rate_limit") or []):
        if not isinstance(limit, dict):
            continue
        for option in ("only", "exclude"):
            if limit.get(option):
                yield "rate_limit", f"`{option}` of `rate_limit`", make_list(limit[option])


def _rate_limit_methods(klass: type) -> t.Iterator[tuple[str, str]]:
    """The options of the rate limits that `klass` declares that name a
    method, and the name."""
    for limit in make_list(vars(klass).get("rate_limit") or []):
        if not isinstance(limit, dict):
            continue
        for option in RATE_LIMIT_METHODS:
            if isinstance(limit.get(option), str):
                yield option, limit[option]
