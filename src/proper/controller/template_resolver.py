"""Template resolution for implicit controller rendering.

Given a controller's prefix chain (its own view folder plus those of its
ancestors) and the request's `Accept` header, pick the best-matching template
from the catalog of views. Falls back through format-less candidates so apps that
don't care about content negotiation keep working unchanged.
"""
import mimetypes
import typing as t
from collections.abc import Iterable, Iterator, Sequence

from ..core.request.headers import parse_accept
from ..views import ComponentNotFoundError


__all__ = (
    "find_template",
    "formats_for",
    "formats_for_header",
    "iter_candidates",
)


# Extension by mime, filled as clients send them. `mimetypes` answers with a
# few dict lookups and a lock; a request should pay for that once, not per
# mime per request. Only mimes `mimetypes` knows get in, so it stays small.
_EXTENSIONS: dict[str, str] = {}


def formats_for(accept: Iterable[str], default_format: str) -> tuple[str, ...]:
    """The filename extensions (without dot) the client accepts, in
    order, or `default_format` alone when it named none we know.

    Stops at `*/*` since anything after it is a wildcard fallback, not a
    preference. But `*/*` means the client takes anything, so
    `default_format` goes after the formats it named: e.g. HTTP libraries
    that send `application/json, text/plain, */*` still get the HTML
    template when there's no JSON or text one.
    Mimes with no registered extension are skipped.
    """
    formats = []
    for mime in accept:
        if mime == "*/*":
            if default_format not in formats:
                formats.append(default_format)
            break
        ext = _EXTENSIONS.get(mime)
        if ext is None:
            guess = mimetypes.guess_extension(mime)
            if not guess:
                continue
            ext = _EXTENSIONS[mime] = guess[1:]
        formats.append(ext)
    return tuple(formats) or (default_format,)


# The formats of each `Accept` header seen so far. Browsers and HTTP
# libraries send the same few, and parsing one costs some microseconds. The
# client chooses the header, so the number kept is bounded: past it, a new
# header is parsed every time.
_FORMATS: dict[tuple[str | None, str], tuple[str, ...]] = {}
MAX_ACCEPT_HEADERS = 256


def formats_for_header(accept: str | None, default_format: str) -> tuple[str, ...]:
    """`formats_for` of an `Accept` header (`None` without one), remembered
    per header."""
    key = (accept, default_format)
    formats = _FORMATS.get(key)
    if formats is None:
        formats = formats_for(parse_accept(accept), default_format)
        if len(_FORMATS) < MAX_ACCEPT_HEADERS:
            _FORMATS[key] = formats
    return formats


def iter_candidates(
    prefixes: Sequence[str],
    action: str,
    formats: Sequence[str],
    handler: str = "jx",
) -> Iterator[str]:
    """Yield template candidate names in priority order.

    For each prefix, emits `{prefix}/{action}.{format}.{handler}` for every
    format, then the bare `{prefix}/{action}.{handler}` as a last-resort
    fallback before moving to the next prefix.
    """
    for prefix in prefixes:
        for fmt in formats:
            yield f"{prefix}/{action}.{fmt}.{handler}"
        yield f"{prefix}/{action}.{handler}"


def find_template(
    catalog: t.Any,
    prefixes: Sequence[str],
    action: str,
    formats: Sequence[str],
    *,
    handler: str = "jx",
    controller: str | None = None,
) -> str:
    """Return the first catalog template matching the prefix/format chain.

    Raises `ComponentNotFoundError` listing every candidate tried if nothing
    matched.
    """
    tried: list[str] = []
    for name in iter_candidates(prefixes, action, formats, handler):
        tried.append(name)
        if catalog.has_component(name):
            return name
    where = f"{controller}.{action}" if controller else f"action `{action}`"
    raise ComponentNotFoundError(
        f"No template found for {where}. Tried: {tried}"
    )
