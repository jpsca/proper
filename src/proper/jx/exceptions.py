"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import typing as t

from .span import error_message


if t.TYPE_CHECKING:
    from .span import Span


class JxException(Exception):
    """Base class for all Jx exceptions."""


class TemplateSyntaxError(JxException):
    """
    Raised when the template syntax is invalid.
    This is usually caused by a missing or extra closing tag.

    The position is kept as data as well as being formatted into the message,
    so a tool can put the error on the right line instead of parsing it back
    out of the text.
    """

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        super().__init__(message)
        self.line = line
        self.col = col

    @classmethod
    def at(cls, name: str, span: "Span", message: str) -> "TemplateSyntaxError":
        """Build the error for a span, keeping its line and column."""
        line, col = span._map.locate(span.start)
        return cls(error_message(name, span, message), line=line, col=col)


class ComponentNotFoundError(JxException):
    """
    Raised when an import fails.
    This is usually caused by a missing or inaccessible component.
    """

    def __init__(self, relpath: str, **kw) -> None:
        msg = f"Component not found: {relpath}"
        super().__init__(msg, **kw)


class MissingRequiredArgument(JxException):
    """
    Raised when a component is used/invoked without passing one or more
    of its required arguments (those without a default value).
    """

    def __init__(self, component: str, arg: str, **kw) -> None:
        msg = f"{component} component requires a `{arg}` argument"
        super().__init__(msg, **kw)


class InvalidPropType(JxException):
    """
    Raised when a component prop has an invalid type.
    """

    def __init__(
        self, component: str, arg: str, expected: type, got: type, **kw
    ) -> None:
        msg = f"{component}: `{arg}` expected {expected.__name__}, got {got.__name__}"
        super().__init__(msg, **kw)


class DuplicateDefDeclaration(JxException):
    """
    Raised when a component has more than one `{#def ... #}` declarations.
    """

    def __init__(self, component: str, **kw) -> None:
        msg = f"{component} has two `{{#def ... #}}` declarations"
        super().__init__(msg, **kw)


class InvalidArgument(JxException):
    """
    Raised when the arguments passed to the component cannot be parsed
    because of an invalid syntax.
    """


class InvalidImport(JxException):
    """
    Raised when the import cannot be parsed
    """


class PathTraversalError(JxException):
    """
    Raised when an import path attempts to escape the component root folder.
    """

    def __init__(self, path: str, **kw) -> None:
        msg = f"Import path escapes component root: {path}"
        super().__init__(msg, **kw)


class MaxRecursionDepthError(JxException):
    """
    Raised when component nesting exceeds the maximum allowed depth.
    """

    def __init__(self, max_depth: int, **kw) -> None:
        msg = f"Maximum component nesting depth exceeded ({max_depth})"
        super().__init__(msg, **kw)


class FileEncodingError(JxException):
    """
    Raised when a component file cannot be read due to encoding issues.
    """

    def __init__(self, path: str, **kw) -> None:
        msg = f"Cannot read {path}: not valid UTF-8"
        super().__init__(msg, **kw)
