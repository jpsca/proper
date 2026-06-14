import typing as t

import babel.lists as babel_lists

from .http import format_locale


if t.TYPE_CHECKING:
    from collections.abc import Sequence


def format_list(
    lst: "Sequence[str]",
    *,
    style: t.Literal[
        "standard",
        "standard-short",
        "or",
        "or-short",
        "unit",
        "unit-short",
        "unit-narrow",
    ] = "standard",
    locale: str = "en",
) -> "Sequence[str]":
    """Format the items in `lst` as a list.

    ```python
    format_list(['apples', 'oranges', 'pears'], locale='en')
    # => 'apples, oranges, and pears'

    format_list(['apples', 'oranges', 'pears'], locale='zh')
    # => 'apples、oranges和pears'

    format_list(['omena', 'peruna', 'aplari'], style='or', locale='fi')
    # => 'omena, peruna tai aplari'
    ```

    Not all styles are necessarily available in all locales.
    The function will attempt to fall back to replacement styles according to the rules
    set forth in the CLDR root XML file, and raise a ValueError if no suitable replacement
    can be found.

    Avaliable styles (from the Unicode TR35-49 spec [1]):

    `standard`
    : A typical 'and' list for arbitrary placeholders. eg. "January, February, and March"

    `standard-short`
    : A short version of an 'and' list, suitable for use with short or abbreviated placeholder values. eg. "Jan., Feb., and Mar."

    `or`
    : A typical 'or' list for arbitrary placeholders. eg. "January, February, or March"

    `or-short`
    : A short version of an 'or' list. eg. "Jan., Feb., or Mar."

    `unit`
    : A list suitable for wide units. eg. "3 feet, 7 inches"

    `unit-short`
    : A list suitable for short units eg. "3 ft, 7 in"

    `unit-narrow`
    : A list suitable for narrow units, where space on the screen is very limited. eg. "3′ 7″"

    Not all styles are necessarily available in all locales.

    [1]: https://www.unicode.org/reports/tr35/tr35-49/tr35-general.html#ListPatterns

    Arguments:
        lst:
            A sequence of items to format in to a list
        style:
            The style to format the list with.
        locale:
            Force the locale to use for formatting.

    """
    return babel_lists.format_list(
        lst,
        style=style,
        locale=format_locale(locale) if locale else None,
    )


def truncate(
    value: str,
    length: int = 255,
    killwords: bool = False,
    end: str = "...",
    leeway: int = 4,
) -> str:
    """Truncate a string to a specified length.

    The length is specified with the second parameter (`length`) which defaults to `255`.
    If the third parameter (`killwords`) is `True` the filter will cut the text at length.
    Otherwise it will discard the last word.

    If the text was in fact truncated it will append an ellipsis sign (`"..."`).
    You can specify a different sign using the fourth (`end`) parameter.

    Strings that only exceed the length by the tolerance margin given in the fifth (`leeway`)
    parameter will not be truncated.

    ```python
    truncate("foo bar baz qux", 9) }}
    # -> "foo..."

    truncate("foo bar baz qux", 9, True) }}
    # -> "foo ba..."

    truncate("foo bar baz qux", 11) }}
    # -> "foo bar baz qux"

    truncate("foo bar baz qux", 11, False, '...', 0) }}
    # -> "foo bar..."
    ```

    Arguments:
        value:
            The string to truncate
        length:
            The maximum length of the returned string, including the `end` string if
            truncation occurs
        killwords:
            Whether to cut the text at length, or discard the last word
        end:
            The string to append if truncation occurs
        leeway:
            The tolerance margin for truncation. Strings that only exceed the length by this
            amount will not be truncated.

    """
    assert length >= len(end), f"expected length >= {len(end)}, got {length}"
    assert leeway >= 0, f"expected leeway >= 0, got {leeway}"

    if len(value) <= length + leeway:
        return value

    if killwords:
        return value[: length - len(end)] + end

    result = value[: length - len(end)].rsplit(" ", 1)[0]
    return result + end


