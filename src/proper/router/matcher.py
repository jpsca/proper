"""A matcher for route patterns, in time linear in the length of the path
or host, for the patterns that Python's `re` could backtrack on.

`Route` compiles each pattern to a regular expression, and `re`
backtracks: for a pattern with several placeholders that can match the
same characters (`:a.:b.:c.example.com`, `/x/:a-:b-:c.html`), a subject
that doesn't match makes it try every way to split the text between the
placeholders, so the time grows with the power of the length (a `Host` of
2 000 dots against `:a.:b.:c.example.com` took seconds).

`LinearPattern` gives the same result as `re.match` of that regular
expression, for every subject, without backtracking. The regular
expression is a sequence of elements followed by the anchor (`/?$` for a
path, `$` for a host), and each element is one of:

- a literal text;
- a greedy run of characters of one class, with a minimum and a maximum
  length (`[^/]+`, `.+`, `[0-9]+`, or a custom format such as `[a-z]+`,
  `\\d{4}` or `[a-z0-9-]{1,63}`);
- an alternation of literal texts (a custom format such as `en|es|pt`),
  tried in order.

`re` finds the first match in this order: the first element takes its
first choice (a run its longest length, an alternation its first text)
with which the rest can still match, and so on. So the matcher first
marks, from the right, the positions from which each element and the ones
after it can match up to the anchor, then walks from the left, giving each
element its first choice that ends at a marked position. Each step is
linear in the length of the subject. On a subject short enough that `re`
reads at most `RE_BUDGET` characters, `LinearPattern.match` uses `re`,
which is faster there.
"""
import re
from math import comb


__all__ = (
    "LinearPattern",
    "linear_pattern",
)

INFINITE = float("inf")

#: `LinearPattern.match` uses `re` (faster on short subjects) when this is
#: more than the characters `re` can read for the subject's size (see
#: `_re_max_size`). The slowest such match measured took about 0.1 ms.
RE_BUDGET = 1_000_000

#: The anchors `Route` puts at the end of a pattern.
PATH_ANCHOR = "/?$"
HOST_ANCHOR = "$"

# The kinds of elements: `(LIT, text)`, `(RUN, atom, min, max)` for a
# greedy run of characters of the class `atom`, `(ALT, texts)`.
LIT, RUN, ALT = "lit", "run", "alt"

#: The built-in formats (`FORMATS` in `route.py`) as elements.
FORMAT_ELEMENTS: "dict[str | None, tuple[tuple, ...]]" = {
    None: ((RUN, r"[^\/]", 1, INFINITE),),
    "path": ((RUN, r".", 1, INFINITE),),
    "int": ((RUN, r"[0-9]", 1, INFINITE),),
    "float": (
        (RUN, r"[0-9]", 1, INFINITE),
        (LIT, "."),
        (RUN, r"[0-9]", 1, INFINITE),
    ),
}

# One character of a class: a set in brackets, a class escape, `.`, an
# escaped symbol, or a character that is not special. A `]` first in a set
# (`[]a]`) is not read here, so such a format is matched with `re`.
_ATOM = (
    r"\[\^?(?:\\.|[^\\\]])(?:\\.|[^\\\]])*\]"
    r"|\\[dDwWsS]"
    r"|\\[^A-Za-z0-9]"
    r"|\."
    r"|[^.^$*+?{}\[\]\\|()]"
)
RX_RUN_FORMAT = re.compile(
    rf"(?P<atom>{_ATOM})"
    r"(?:(?P<op>[+*?])|\{(?P<min>\d*)(?P<comma>,?)(?P<max>\d*)\})"
)
RX_LITERAL = re.compile(r"(?:[A-Za-z0-9_\-]|\\[^A-Za-z0-9])+")


def _custom_elements(fmt: str) -> tuple | None:
    """The elements of a custom format, or `None` if it is not one this
    module can match: a greedy run of one class of characters
    (`[a-z]+`, `\\d{4}`, `[^.]{1,63}`), or literal texts separated by `|`
    (`en|es|pt`)."""
    # `fmt` is known to compile: `Route` compiled the whole pattern first.
    m = RX_RUN_FORMAT.fullmatch(fmt)
    if m is not None:
        op = m["op"]
        if op:
            low, high = {"+": (1, INFINITE), "*": (0, INFINITE), "?": (0, 1)}[op]
        elif m["min"] or m["max"]:
            low = int(m["min"] or 0)
            high = int(m["max"]) if m["max"] else (INFINITE if m["comma"] else low)
        else:
            return None
        return ((RUN, m["atom"], low, high),)

    texts = fmt.split("|")
    if all(RX_LITERAL.fullmatch(text) for text in texts):
        # Remove the backslash of each escaped symbol.
        return ((ALT, tuple(re.sub(r"\\(.)", r"\1", text) for text in texts)),)
    return None


class _Class:
    """A class of characters, from one `atom` of a regular expression."""

    __slots__ = ("one", "runs_re")

    def __init__(self, atom: str) -> None:
        self.one = re.compile(atom)
        self.runs_re = re.compile(f"(?:{atom})+")

    def has(self, char: str) -> bool:
        return self.one.fullmatch(char) is not None

    def runs(self, subject: str) -> list[int]:
        """Per position, how many characters of the class start there."""
        result = [0] * (len(subject) + 1)
        for m in self.runs_re.finditer(subject):
            end = m.end()
            for pos in range(m.start(), end):
                result[pos] = end - pos
        return result


class LinearPattern:
    """A compiled pattern: literals, runs and alternations, then an anchor.

    `match(subject)` returns the values of the placeholders, as
    `re.match(...).groupdict()` of the route's regular expression `regex`
    would, or `None`.
    """

    __slots__ = ("elements", "groups", "anchor", "classes", "regex", "re_max_size")

    def __init__(
        self, elements: list, groups: list, anchor: str, regex: re.Pattern
    ) -> None:
        #: `(LIT, text)`, `(RUN, atom, min, max)` or `(ALT, texts)`.
        self.elements = tuple(elements)
        #: `(name, first element, element after the last)` per placeholder.
        self.groups = tuple(groups)
        self.anchor = anchor
        self.classes = {
            element[1]: _Class(element[1])
            for element in elements
            if element[0] == RUN
        }
        self.regex = regex
        self.re_max_size = _re_max_size(self.elements)

    def match(self, subject: str) -> dict | None:
        if len(subject) <= self.re_max_size:
            m = self.regex.match(subject)
            return None if m is None else m.groupdict()
        return self.match_linear(subject)

    def match_linear(self, subject: str) -> dict | None:
        """`match` without `re`, whatever the size of `subject`."""
        size = len(subject)
        runs = {atom: cls.runs(subject) for atom, cls in self.classes.items()}
        elements = self.elements

        # `ok[i][pos]`: element `i` and the ones after it, then the anchor,
        # can match from `pos`.
        ok = [bytearray(size + 1) for _ in range(len(elements) + 1)]
        last = ok[-1]
        # `$` matches at the end, or before a newline at the end.
        dollar_at = [size]
        if size and subject[-1] == "\n":
            dollar_at.append(size - 1)
        for pos in dollar_at:
            last[pos] = 1
            # `/?` before `$` takes a `/` there.
            if self.anchor == PATH_ANCHOR and pos and subject[pos - 1] == "/":
                last[pos - 1] = 1

        for index in range(len(elements) - 1, -1, -1):
            kind, *args = elements[index]
            after = ok[index + 1]
            here = ok[index]
            if kind == RUN:
                atom, low, high = args
                run = runs[atom]
                # `following[pos]`: the first position from `pos` on from
                # which the rest matches (`size + 1` if none).
                following = [size + 1] * (size + 2)
                for pos in range(size, -1, -1):
                    following[pos] = pos if after[pos] else following[pos + 1]
                for pos in range(size + 1):
                    if run[pos] >= low and following[min(pos + low, size + 1)] <= (
                        pos + min(run[pos], high)
                    ):
                        here[pos] = 1
            else:
                for text in args[0] if kind == ALT else args:
                    width = len(text)
                    for pos in range(size - width + 1):
                        if after[pos + width] and subject.startswith(text, pos):
                            here[pos] = 1

        if not ok[0][0]:
            return None

        # Walk from the left: each element takes its first choice after
        # which the rest still matches, the one `re` finds first.
        bounds = [0]
        pos = 0
        for index, (kind, *args) in enumerate(elements):
            after = ok[index + 1]
            if kind == LIT:
                pos += len(args[0])
            elif kind == RUN:
                atom, low, high = args
                end = pos + min(runs[atom][pos], high)
                while not after[end]:
                    end -= 1
                pos = end
            else:
                for text in args[0]:  # pragma: no branch
                    if subject.startswith(text, pos) and after[pos + len(text)]:
                        pos += len(text)
                        break
            bounds.append(pos)

        return {
            name: subject[bounds[first] : bounds[stop]]
            for name, first, stop in self.groups
        }


def _re_max_size(elements: tuple) -> int:
    """The size of the longest subject on which `re` reads at most
    `RE_BUDGET` characters.

    `re` tries the choices of each element in order, so it tries each list
    of the places where the elements with a choice end at most once: at
    most `comb(size + choices, choices)` lists of `choices` positions in
    order. For each, it goes through `len(elements)` elements, and each
    reads at most `size + 1` characters, or a literal's length.
    """
    choices = sum(
        1
        for element in elements
        if (element[0] == RUN and element[2] != element[3])
        or (element[0] == ALT and len(element[1]) > 1)
    )
    longest = max((len(e[1]) for e in elements if e[0] == LIT), default=0)
    size = 0
    while (
        comb(size + 1 + choices, choices) * len(elements) * (size + 2 + longest)
        <= RE_BUDGET
    ):
        size += 1
    return size


def _ends_in_one_place(element: tuple, next_text: str) -> bool:
    """Can a placeholder whose last element is `element` end in only one
    place, when `next_text` (maybe empty) follows it?"""
    if element[0] == RUN:
        _, atom, low, high = element
        if low == high:
            return True
        return bool(next_text) and not _Class(atom).has(next_text[0])
    # An alternation: in one place unless a text starts another one.
    texts = element[1]
    return not any(a != b and b.startswith(a) for a in texts for b in texts)


def linear_pattern(
    pieces: "list[tuple[str, str | None]]",
    formats: "dict[str, str | None]",
    anchor: str,
    regex: re.Pattern,
) -> LinearPattern | None:
    """A `LinearPattern` for the pattern made of `pieces` (as
    `_compile_pattern` gives them, with the format of each placeholder in
    `formats`), or `None` when the regular expression is used instead.

    The regular expression is used:

    - when `re` can't backtrack much: every placeholder but the last one
      ends in only one place, because the text after it can't start with a
      character it takes (`/posts/:id/edit`, `/:year<\\d{4}>-:slug`). Then
      `re` takes time linear in the length of the subject and, for routes
      without a host, matches many routes in one call;
    - when a placeholder has a custom format this module can't match (see
      `_custom_elements`); then the time is that of `re` on the pattern.
    """
    names = [name for _, name in pieces if name is not None]
    if len(names) < 2:
        return None
    per_name = {}
    for name in names:
        fmt = formats[name]
        if fmt in FORMAT_ELEMENTS:
            found = FORMAT_ELEMENTS[fmt]
        else:
            found = _custom_elements(fmt)  # type: ignore[arg-type]
            if found is None:
                return None
        per_name[name] = found

    elements: list[tuple] = []
    groups: list[tuple[str, int, int]] = []
    backtracks = False
    previous: tuple | None = None
    for literal, name in pieces:
        if previous is not None and name is not None:
            # The placeholder before this literal is not the last one.
            backtracks = backtracks or not _ends_in_one_place(previous, literal)
        if literal:
            elements.append((LIT, literal))
        if name is None:
            break
        first = len(elements)
        elements.extend(per_name[name])
        groups.append((name, first, len(elements)))
        previous = elements[-1]

    if not backtracks:
        return None
    return LinearPattern(elements, groups, anchor, regex)
