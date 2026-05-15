"""Template resolution for implicit controller rendering.

Given a controller's prefix chain (its own view folder plus those of its
ancestors) and the request's `Accept` header, pick the best-matching template
from the jx catalog. Falls back through format-less candidates so apps that
don't care about content negotiation keep working unchanged.
"""
import mimetypes
import typing as t

from jx import ComponentNotFoundError


__all__ = ("iter_format_extensions", "iter_candidates", "resolve_template")


def iter_format_extensions(accept: "t.Iterable[str]") -> "t.Iterator[str]":
    """Yield filename extensions (without dot) for each mime in `accept`.

    Stops at `*/*` since anything after it is a wildcard fallback, not a
    preference. Mimes with no registered extension are skipped.
    """
    for mime in accept:
        if mime == "*/*":
            return
        ext = mimetypes.guess_extension(mime)
        if ext:
            yield ext[1:]


def iter_candidates(
    prefixes: "t.Sequence[str]",
    action: str,
    formats: "t.Sequence[str]",
    handler: str = "jx",
) -> "t.Iterator[str]":
    """Yield template candidate names in priority order.

    For each prefix, emits `{prefix}/{action}.{format}.{handler}` for every
    format, then the bare `{prefix}/{action}.{handler}` as a last-resort
    fallback before moving to the next prefix.
    """
    for prefix in prefixes:
        for fmt in formats:
            yield f"{prefix}/{action}.{fmt}.{handler}"
        yield f"{prefix}/{action}.{handler}"


def resolve_template(
    catalog: t.Any,
    prefixes: "t.Sequence[str]",
    action: str,
    *,
    accept: "t.Iterable[str]",
    default_format: str,
    handler: str = "jx",
    controller: str | None = None,
) -> str:
    """Return the first catalog template matching the prefix/format chain.

    Raises `ComponentNotFoundError` listing every candidate tried if nothing
    matched.
    """
    formats = list(iter_format_extensions(accept)) or [default_format]
    tried: list[str] = []
    for name in iter_candidates(prefixes, action, formats, handler):
        tried.append(name)
        if catalog.has(name):
            return name
    where = f"{controller}.{action}" if controller else f"action `{action}`"
    raise ComponentNotFoundError(
        f"No template found for {where}. Tried: {tried}"
    )
