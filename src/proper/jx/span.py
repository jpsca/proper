"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from bisect import bisect_right


class Span:
    """
    A region of the template source.

    Line and column are resolved on demand. Most spans are only ever used to
    locate an error that never happens, so paying for the lookup up front would
    be paying for nothing on every token of every template.
    """

    __slots__ = ("start", "end", "_map")

    def __init__(self, start: int, end: int, source_map: "SourceMap") -> None:
        self.start = start
        self.end = end
        self._map = source_map

    @property
    def line(self) -> int:
        """1-based."""
        return self._map.locate(self.start)[0]

    @property
    def col(self) -> int:
        """0-based, to match the caret column in error messages."""
        return self._map.locate(self.start)[1]

    @property
    def text(self) -> str:
        return self._map.source[self.start : self.end]

    def __repr__(self) -> str:
        return f"Span({self.line}:{self.col})"


class SourceMap:
    """
    Resolves offsets to line/column.

    The line starts are indexed once, so locating a position is a binary search
    instead of counting newlines from the top of the file for every lookup.
    """

    __slots__ = ("source", "_starts")

    def __init__(self, source: str) -> None:
        self.source = source
        starts = [0]
        pos = source.find("\n")
        while pos != -1:
            starts.append(pos + 1)
            pos = source.find("\n", pos + 1)
        self._starts = starts

    def locate(self, offset: int) -> tuple[int, int]:
        """Return the (1-based line, 0-based column) of an offset."""
        index = bisect_right(self._starts, offset) - 1
        return index + 1, offset - self._starts[index]

    def span(self, start: int, end: int) -> Span:
        return Span(start, end, self)

    def line_text(self, line: int) -> str:
        """Return the text of a 1-based line, without its newline."""
        if line < 1 or line > len(self._starts):
            return ""
        start = self._starts[line - 1]
        end = self.source.find("\n", start)
        return self.source[start:] if end == -1 else self.source[start:end]


def error_message(name: str, span: Span, message: str) -> str:
    """
    Format a syntax error as `[template:line:col] message`, followed by the
    offending line and a caret under the exact column.
    """
    line, col = span._map.locate(span.start)
    return (
        f"[{name}:{line}:{col}] {message}\n"
        f"  {span._map.line_text(line)}\n"
        f"  {' ' * col}^"
    )
