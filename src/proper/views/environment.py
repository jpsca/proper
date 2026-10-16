"""
minijx runtime: the filters and tests a catalog renders with.

The generated code looks filters and tests up by name, in the dicts it finds
in `_globals` under `__minijx_filters__` (or `__minijx_filters_ae__` for
components compiled with autoescape) and `__minijx_tests__`, or in the
builtin ones. A catalog with custom filters or tests builds its dicts here.
"""

import typing as t

from .filters import FILTERS, FILTERS_AE, bound_to
from .tests import INLINE_TESTS, TESTS


FILTERS_KEY = "__minijx_filters__"
FILTERS_AE_KEY = "__minijx_filters_ae__"
TESTS_KEY = "__minijx_tests__"


def build(
    filters: "dict[str, t.Callable] | None" = None,
    tests: "dict[str, t.Callable] | None" = None,
) -> "tuple[dict[str, t.Callable], dict[str, t.Callable], dict[str, t.Callable]]":
    """
    The builtin filters and tests plus the custom ones, which win on a name
    clash (as in Jx, a custom filter can replace a builtin one).

    `map`, `select` and friends, and the `filter` and `test` tests, are
    rebound so they see the custom names too, unless they were replaced.

    Returns the filters, the filters for components compiled with
    autoescape, and the tests.
    """
    filters = dict(filters or {})
    tests = dict(tests or {})
    inline = sorted(INLINE_TESTS & tests.keys())
    if inline:
        raise ValueError(
            f"Cannot replace the test(s) {', '.join(map(repr, inline))}: minijx compiles "
            "them into plain Python instead of calling a function"
        )
    for name, value in (*filters.items(), *tests.items()):
        if not callable(value):
            raise TypeError(f"{name!r} is not callable")

    all_tests = {**TESTS, **tests}
    all_filters = {**FILTERS, **filters}
    ae_filters = {**FILTERS_AE, **filters}
    for table in (all_filters, ae_filters):
        for name, func in bound_to(table, all_tests).items():
            if name not in filters:
                table[name] = func
    if "filter" not in tests:
        all_tests["filter"] = all_filters.__contains__
    if "test" not in tests:
        all_tests["test"] = all_tests.__contains__
    return all_filters, ae_filters, all_tests
