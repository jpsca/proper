"""
minijx runtime: Jinja's builtin tests.

Each function takes the tested value first, then the test's arguments.
`defined`/`undefined` cannot see Jinja's Undefined, so the compiler emits
`"name" in _globals` / `has_attr(obj, name)` for those instead; the
functions here exist so `select("defined")` and friends still resolve.
"""

import builtins
import operator
import typing as t
from collections import abc
from numbers import Number


def test_odd(value):
    return value % 2 == 1


def test_even(value):
    return value % 2 == 0


def test_divisibleby(value, num):
    return value % num == 0


def test_defined(value):
    return value is not None


def test_undefined(value):
    return value is None


def test_filter(value):
    from .filters import FILTERS

    return value in FILTERS


def test_test(value):
    return value in TESTS


def test_none(value):
    return value is None


def test_boolean(value):
    return value is True or value is False


def test_false(value):
    return value is False


def test_true(value):
    return value is True


def test_integer(value):
    return isinstance(value, int) and value is not True and value is not False


def test_float(value):
    return isinstance(value, builtins.float)


def test_lower(value):
    return str(value).islower()


def test_upper(value):
    return str(value).isupper()


def test_string(value):
    return isinstance(value, str)


def test_mapping(value):
    return isinstance(value, abc.Mapping)


def test_number(value):
    return isinstance(value, Number)


def test_sequence(value):
    # Same as Jinja's: it has a length and can be indexed.
    try:
        len(value)
    except Exception:
        return False
    return hasattr(value, "__getitem__")


def test_sameas(value, other):
    return value is other


def test_iterable(value):
    try:
        iter(value)
    except TypeError:
        return False
    return True


def test_escaped(value):
    return hasattr(value, "__html__")


def test_in(value, seq):
    return value in seq


def test_callable(value):
    return callable(value)


TESTS: dict[str, t.Callable] = {
    "odd": test_odd,
    "even": test_even,
    "divisibleby": test_divisibleby,
    "defined": test_defined,
    "undefined": test_undefined,
    "filter": test_filter,
    "test": test_test,
    "none": test_none,
    "boolean": test_boolean,
    "false": test_false,
    "true": test_true,
    "integer": test_integer,
    "float": test_float,
    "lower": test_lower,
    "upper": test_upper,
    "string": test_string,
    "mapping": test_mapping,
    "number": test_number,
    "sequence": test_sequence,
    "iterable": test_iterable,
    "callable": test_callable,
    "sameas": test_sameas,
    "escaped": test_escaped,
    "in": test_in,
    "==": operator.eq,
    "eq": operator.eq,
    "equalto": operator.eq,
    "!=": operator.ne,
    "ne": operator.ne,
    ">": operator.gt,
    "gt": operator.gt,
    "greaterthan": operator.gt,
    ">=": operator.ge,
    "ge": operator.ge,
    "<": operator.lt,
    "lt": operator.lt,
    "lessthan": operator.lt,
    "<=": operator.le,
    "le": operator.le,
}

# Names the compiler can emit as `_t.<name>(...)`; operators map to these.
ALIASES = {
    "==": "eq", "!=": "ne", ">": "gt", ">=": "ge", "<": "lt", "<=": "le",
}
eq, ne, gt, ge, lt, le = operator.eq, operator.ne, operator.gt, operator.ge, operator.lt, operator.le
equalto, greaterthan, lessthan = eq, gt, lt

odd, even, divisibleby, defined, undefined = test_odd, test_even, test_divisibleby, test_defined, test_undefined
filter, test, none, boolean, false, true = test_filter, test_test, test_none, test_boolean, test_false, test_true
integer, float, lower, upper, string = test_integer, test_float, test_lower, test_upper, test_string
mapping, number, sequence, iterable, callable_ = test_mapping, test_number, test_sequence, test_iterable, test_callable
sameas, escaped = test_sameas, test_escaped
in_ = test_in


# Tests the compiler turns into plain Python instead of calling them
# (`x is defined` -> `"x" in _globals`, `x is eq y` -> `x == y`, ...), so a
# custom test with one of these names would never be called.
INLINE_TESTS = frozenset({
    "defined", "undefined", "none", "in", "callable", "sameas",
    "eq", "equalto", "==", "ne", "!=", "gt", "greaterthan", ">",
    "ge", ">=", "lt", "lessthan", "<", "le", "<=",
})
