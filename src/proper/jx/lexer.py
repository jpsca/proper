"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import re
from dataclasses import dataclass
from enum import Enum

from .exceptions import TemplateSyntaxError
from .span import SourceMap, Span


TAG_NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
TAG_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:$-"
)
# A component tag name must be followed by one of these, so `<Hr` in the middle
# of a word is not mistaken for a tag.
TAG_NAME_END = frozenset(" \t\r\n/>")

ATTR_NAME_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ:@$_")
ATTR_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@:$_-."
)

WHITESPACE = frozenset(" \t\r\n")
KEYWORD_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz_")

# The `{# … #}` declarations that may appear in a component's header.
DECLARATION_KEYWORDS = frozenset({"def", "import", "css", "js"})

# The end of a raw block, spelled exactly as Jinja's own lexer spells it. Jx
# hands the block through verbatim, so the two have to agree on where it ends.
RAW_END_RE = re.compile(r"\{%[-+]?\s*endraw\s*[-+]?%\}")

OPEN_BRACKETS = frozenset("([{")
CLOSE_BRACKETS = frozenset(")]")


class TokenType(Enum):
    TEXT = "text"
    EXPR = "expr"  # {{ … }}
    STMT = "stmt"  # {% … %}
    COMMENT = "comment"  # {# … #}
    RAW = "raw"  # {% raw %} … {% endraw %}
    TAG_OPEN = "tag_open"  # <Name …>  or  <Name … />
    TAG_CLOSE = "tag_close"  # </Name>


class AttrKind(Enum):
    FLAG = "flag"  # `disabled`, no value
    STRING = "string"  # `x="y"` — the source text, quotes included
    EXPR = "expr"  # `x={{ y }}` — the source text, braces included


@dataclass(slots=True)
class Attribute:
    name: str  # exactly as written in the source
    value: str | None  # raw source text of the value; None for a flag
    kind: AttrKind
    span: Span
    value_span: Span | None = None


@dataclass(slots=True)
class Token:
    type: TokenType
    value: str  # the raw source text this token covers
    span: Span
    name: str = ""  # tag name, or statement keyword
    attrs: tuple[Attribute, ...] = ()
    self_closing: bool = False
    lstrip: bool = False  # the statement's opening `-`
    rstrip: bool = False  # the statement's closing `-`


class Lexer:
    """
    Turns template source into a flat token stream.

    The lexer decides where every construct *ends*; it does not look inside a
    Jinja expression or statement. Delimiting `{{ … }}` correctly needs quote
    and bracket tracking, but nothing here needs to understand `a.b | c`.
    """

    def __init__(self, name: str, source: str) -> None:
        self.name = name
        self.source = source
        self.map = SourceMap(source)

    # Errors

    def error(self, offset: int, message: str) -> TemplateSyntaxError:
        span = self.map.span(offset, offset)
        return TemplateSyntaxError.at(self.name, span, message)

    # Public

    def tokens(self) -> list[Token]:
        src = self.source
        end = len(src)
        out: list[Token] = []
        pos = 0
        text_start = 0

        # Two cursors, refreshed only once the position passes them. Searching
        # for both delimiters on every iteration would rescan the whole rest of
        # the source for `{` at each of the `<` in a plain HTML template, which
        # is quadratic in the number of candidates.
        brace = src.find("{", pos)
        angle = src.find("<", pos)

        while pos < end:
            if brace == -1:
                nxt = angle
            elif angle == -1:
                nxt = brace
            else:
                nxt = min(brace, angle)
            if nxt == -1:
                break

            token = self._construct_at(nxt)
            if token is None:
                # Not a construct after all: an ordinary `{` or `<` in the text.
                pos = nxt + 1
            else:
                if nxt > text_start:
                    out.append(self._text(text_start, nxt))
                out.append(token)
                pos = text_start = token.span.end

            # Each of these resumes where it left off, so across the whole loop
            # the two searches cover the source once each.
            if brace != -1 and brace < pos:
                brace = src.find("{", pos)
            if angle != -1 and angle < pos:
                angle = src.find("<", pos)

        if text_start < end:
            out.append(self._text(text_start, end))

        return out

    # Private

    def _text(self, start: int, end: int) -> Token:
        return Token(
            type=TokenType.TEXT,
            value=self.source[start:end],
            span=self.map.span(start, end),
        )

    def _construct_at(self, i: int) -> Token | None:
        src = self.source
        pair = src[i : i + 2]
        if pair == "{{":
            return self._scan_expr(i)
        if pair == "{%":
            return self._scan_stmt(i)
        if pair == "{#":
            return self._scan_comment(i)
        if pair == "</":
            return self._scan_close_tag(i)
        if src[i] == "<":
            return self._scan_open_tag(i)
        return None

    def _find_expr_end(self, i: int, *, nested_is_error: bool = True) -> int:
        """
        Return the offset just past the `}}` that closes the `{{` at `i`.

        Quotes are honoured, and so is bracket depth, so `{{ {'a': 1} }}` and
        `{{ d['}}'] }}` both close where a reader would expect.
        """
        src = self.source
        end = len(src)
        j = i + 2
        depth = 0
        quote = ""

        while j < end:
            ch = src[j]
            if quote:
                if ch == "\\":
                    j += 2
                    continue
                if ch == quote:
                    quote = ""
                j += 1
                continue
            if ch in "\"'":
                quote = ch
                j += 1
                continue
            if nested_is_error and src[j : j + 2] == "{{":
                # Checked before the bracket count, or the first `{` of a
                # nested `{{` would just look like an open brace.
                raise self.error(i, "Unmatched braces")
            if ch in OPEN_BRACKETS:
                depth += 1
                j += 1
                continue
            if ch in CLOSE_BRACKETS:
                depth -= 1
                j += 1
                continue
            if ch == "}":
                if depth == 0 and src[j : j + 2] == "}}":
                    return j + 2
                depth -= 1
                j += 1
                continue
            j += 1

        raise self.error(i, "Unclosed expression '{{'")

    def _scan_expr(self, i: int) -> Token:
        end = self._find_expr_end(i)
        return Token(
            type=TokenType.EXPR,
            value=self.source[i:end],
            span=self.map.span(i, end),
        )

    def _scan_comment(self, i: int) -> Token:
        end = self.source.find("#}", i + 2)
        if end == -1:
            raise self.error(i, "Unclosed comment '{#'")
        end += 2
        return Token(
            type=TokenType.COMMENT,
            value=self.source[i:end],
            span=self.map.span(i, end),
        )

    def _stmt_parts(self, i: int) -> tuple[str, bool, bool, int]:
        """
        Scan the `{% … %}` starting at `i`.

        Returns its keyword, its two whitespace-control flags, and the offset
        just past the closing `%}`.
        """
        src = self.source
        end = len(src)
        j = i + 2
        # `-` strips the whitespace before the tag, `+` explicitly keeps it.
        # Both have to be stepped over, or the keyword comes out empty and the
        # tag stops being recognized at all.
        marker = src[j : j + 1]
        lstrip = marker == "-"
        if marker in ("-", "+"):
            j += 1

        while j < end and src[j] in WHITESPACE:
            j += 1
        kw_start = j
        while j < end and src[j] in KEYWORD_CHARS:
            j += 1
        keyword = src[kw_start:j]

        quote = ""
        while j < end:
            ch = src[j]
            if quote:
                if ch == "\\":
                    j += 2
                    continue
                if ch == quote:
                    quote = ""
                j += 1
                continue
            if ch in "\"'":
                quote = ch
                j += 1
                continue
            if src[j : j + 2] == "%}":
                rstrip = src[j - 1 : j] == "-"
                return keyword, lstrip, rstrip, j + 2
            j += 1

        raise self.error(i, "Unclosed statement '{%'")

    def _scan_stmt(self, i: int) -> Token:
        keyword, lstrip, rstrip, end = self._stmt_parts(i)
        if keyword == "raw":
            return self._scan_raw(i, end)
        return Token(
            type=TokenType.STMT,
            value=self.source[i:end],
            span=self.map.span(i, end),
            name=keyword,
            lstrip=lstrip,
            rstrip=rstrip,
        )

    def _scan_raw(self, i: int, body_start: int) -> Token:
        """
        A raw block is one opaque token: nothing inside it is a construct.

        So look for the terminator and nothing else. Scanning the `{%` in
        between as statements would make `{% raw %}Use {% here{% endraw %}`
        an error, when the whole point of the block is that it is text.
        """
        match = RAW_END_RE.search(self.source, body_start)
        if match is None:
            raise self.error(i, "Unclosed '{% raw %}'")
        after = match.end()
        return Token(
            type=TokenType.RAW,
            value=self.source[i:after],
            span=self.map.span(i, after),
            name="raw",
        )

    def _scan_close_tag(self, i: int) -> Token | None:
        src = self.source
        end = len(src)
        j = i + 2
        if j >= end or src[j] not in TAG_NAME_START:
            return None
        while j < end and src[j] in TAG_NAME_CHARS:
            j += 1
        if j >= end or src[j] != ">":
            return None
        name = src[i + 2 : j]
        return Token(
            type=TokenType.TAG_CLOSE,
            value=src[i : j + 1],
            span=self.map.span(i, j + 1),
            name=name,
        )

    def _scan_open_tag(self, i: int) -> Token | None:
        src = self.source
        end = len(src)
        j = i + 1
        if j >= end or src[j] not in TAG_NAME_START:
            return None
        while j < end and src[j] in TAG_NAME_CHARS:
            j += 1
        if j >= end or src[j] not in TAG_NAME_END:
            return None
        name = src[i + 1 : j]

        attrs, self_closing, tag_end = self._scan_attrs(i, name, j)
        return Token(
            type=TokenType.TAG_OPEN,
            value=src[i:tag_end],
            span=self.map.span(i, tag_end),
            name=name,
            attrs=tuple(attrs),
            self_closing=self_closing,
        )

    def _scan_attrs(
        self, tag_start: int, tag: str, j: int
    ) -> tuple[list[Attribute], bool, int]:
        src = self.source
        end = len(src)
        attrs: list[Attribute] = []
        # Keyed by the normalized name, because `data-id` and `data_id` both
        # reach the generated code as the same `data_id` keyword.
        seen: set[str] = set()

        def syntax_error() -> TemplateSyntaxError:
            span = self.map.span(tag_start, tag_start)
            return TemplateSyntaxError.at(self.name, span, f"Syntax error: `{tag}`")

        while True:
            while j < end and src[j] in WHITESPACE:
                j += 1
            if j >= end:
                raise syntax_error()

            if src[j] == ">":
                return attrs, False, j + 1
            if src[j] == "/":
                if src[j + 1 : j + 2] != ">":
                    raise syntax_error()
                return attrs, True, j + 2

            name_start = j
            if src[j] not in ATTR_NAME_START:
                raise syntax_error()
            j += 1
            while j < end and src[j] in ATTR_NAME_CHARS:
                j += 1
            name = src[name_start:j]

            k = j
            while k < end and src[k] in WHITESPACE:
                k += 1

            if k < end and src[k] == "=":
                k += 1
                while k < end and src[k] in WHITESPACE:
                    k += 1
                value, kind, value_span, j = self._scan_attr_value(k, syntax_error)
            else:
                value, kind, value_span = None, AttrKind.FLAG, None

            key = name.replace("-", "_")
            if key in seen:
                span = self.map.span(name_start, j)
                raise TemplateSyntaxError.at(
                    self.name, span, f"Duplicate attribute `{name}` on `{tag}`"
                )
            seen.add(key)
            attrs.append(
                Attribute(
                    name=name,
                    value=value,
                    kind=kind,
                    span=self.map.span(name_start, j),
                    value_span=value_span,
                )
            )

    def _scan_attr_value(self, k: int, syntax_error):
        src = self.source
        end = len(src)
        ch = src[k] if k < end else ""

        if ch in "\"'":
            j = k + 1
            while j < end:
                if src[j] == "\\":
                    j += 2  # an escaped quote does not end the value
                    continue
                if src[j] == ch:
                    stop = j + 1
                    return src[k:stop], AttrKind.STRING, self.map.span(k, stop), stop
                j += 1
            raise syntax_error()

        if src[k : k + 2] == "{{":
            try:
                stop = self._find_expr_end(k)
            except TemplateSyntaxError as err:
                if "Unmatched braces" in str(err):
                    raise
                raise syntax_error() from err
            return src[k:stop], AttrKind.EXPR, self.map.span(k, stop), stop

        # Anything else is ambiguous: is `title=hello` the string "hello" or the
        # variable `hello`? Refuse instead of guessing.
        tag_end = src.find(">", k)
        rest = src[k:] if tag_end == -1 else src[k:tag_end]
        if "}}" in rest:
            raise self.error(k, "Unmatched braces")
        raise TemplateSyntaxError.at(
            self.name,
            self.map.span(k, k),
            "Attribute values must be quoted or wrapped in {{ \u2026 }}",
        )


def split_declaration(comment: str) -> tuple[str, str, int] | None:
    """
    Split a `{# def … #}` style comment into its keyword and its payload.

    Returns `(keyword, payload, payload_offset)`, the offset being where the
    payload starts within `comment` — an editor needs it to point at a piece of
    a declaration rather than at the whole comment.

    Returns `None` for an ordinary comment, and for a declaration keyword that
    is not followed by anything (`{# def #}`), which has always been a no-op.
    """
    inner = comment[2:-2]
    # How far `inner` sits into `comment`, so payload offsets can be reported
    # against the comment the caller passed in.
    base = 2
    if inner[:1] == "-":
        inner = inner[1:]
        base += 1
    if inner[-1:] == "-":
        inner = inner[:-1]

    i = 0
    end = len(inner)
    while i < end and inner[i] in WHITESPACE:
        i += 1
    start = i
    while i < end and inner[i] in KEYWORD_CHARS:
        i += 1
    keyword = inner[start:i]

    if keyword not in DECLARATION_KEYWORDS:
        return None
    # The keyword has to be separated from its payload.
    if i >= end or inner[i] not in WHITESPACE:
        return None
    rest = inner[i:]
    payload = rest.strip()
    if not payload:
        return None
    return keyword, payload, base + i + (len(rest) - len(rest.lstrip()))


def scan_header(source: str) -> list[tuple[str, str, int, int]]:
    """
    Read the run of `{# … #}` comments a component starts with.

    Only the header is scanned, never the body: metadata has to be readable
    from a template whose markup is broken, because that is exactly when a
    tool wants to say which component the error is in.

    Returns:
        `(keyword, payload, offset, payload_offset)` for each declaration
        found, both offsets absolute within `source`.

    """
    out: list[tuple[str, str, int, int]] = []
    pos = 0
    end = len(source)

    while pos < end:
        while pos < end and source[pos] in WHITESPACE:
            pos += 1
        if source[pos : pos + 2] != "{#":
            break
        close = source.find("#}", pos + 2)
        if close == -1:
            break
        close += 2
        found = split_declaration(source[pos:close])
        if found:
            out.append((found[0], found[1], pos, pos + found[2]))
        pos = close

    return out


def strip_inline_comments(text: str) -> str:
    """
    Drop `# …` comments from a declaration's payload, keeping any `#` that is
    inside a quoted string — asset URLs use them as fragments.
    """
    out: list[str] = []
    quote = ""
    i = 0
    end = len(text)

    while i < end:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            while out and out[-1] in " \t\r\n":
                out.pop()
            while i < end and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1

    return "".join(out)
