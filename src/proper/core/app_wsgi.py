"""WSGI: the sync face of the app.

The server calls `app(environ, start_response)` on one of its own threads, so
the pipeline runs right there: no event loop, no hand-off to a worker. The
WebSockets are the cable's (`proper.channels.cable`).

`proper run` serves `app._bearings` instead, with Bearings' raw interface:
the same pipeline, with the request built from the head Bearings parsed, and
no environ in between.
"""
import contextvars
import typing as t
from http import HTTPStatus
from urllib.parse import unquote_to_bytes

from ..errors import BadRequest
from ..global_context import current
from ..helpers import MultiDict


if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from bearings import Listener

    from ..app import App
    from ..core.request import Request
    from ..core.response import Response


def _reason(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return ""


def _address(host: str | None, port: str | None) -> "tuple[str, int | None] | None":
    if not host:
        return None
    return (host, int(port) if port and port.isdigit() else None)


def _headers_from_environ(environ: dict) -> "list[tuple[str, str]]":
    """The request headers WSGI folds into `environ`: `HTTP_*`, plus the two
    it keeps apart."""
    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers.append((key[5:].replace("_", "-").lower(), value))
    if environ.get("CONTENT_TYPE"):
        headers.append(("content-type", environ["CONTENT_TYPE"]))
    if environ.get("CONTENT_LENGTH"):
        headers.append(("content-length", environ["CONTENT_LENGTH"]))
    return headers


def _headers_from_head(fields: "list[str]") -> MultiDict:
    """The headers of a head Bearings parsed (`name, value, ...` from
    `fields[6]` on), as the environ would give them: names in lowercase,
    those with `_` dropped (CGI would read them as the same name with `-`),
    and a repeated header in one value, joined with commas (`; ` for
    `cookie`)."""
    headers = MultiDict()
    data = headers.data
    for i in range(6, len(fields) - 1, 2):
        name = fields[i].lower()
        if "_" in name:
            continue
        values = data.get(name)
        if values is None:
            data[name] = [fields[i + 1]]
        else:
            values[0] += ("; " if name == "cookie" else ",") + fields[i + 1]
    return headers


def _path_from_head(path: str) -> str:
    """The path as the client sent it (percent-escapes kept, latin-1), decoded
    as UTF-8."""
    if "%" in path:
        return unquote_to_bytes(path).decode("utf-8", "replace")
    if path.isascii():
        return path or "/"
    return path.encode("latin-1").decode("utf-8", "replace")


class AppWsgi:
    """A mixin that makes the app a WSGI callable, and the callable of
    Bearings' raw interface (`_bearings`)."""

    config: t.Any
    request_cls: t.Any
    response_cls: t.Any

    def __call__(
        self: "App", environ: dict, start_response: "Callable"
    ) -> "Iterable[bytes]":
        try:
            request = self._request_from_environ(environ)
            error = None
        except BadRequest as exc:
            # A header the request can't be built with, such as an invalid
            # `Host` (the server passes it as the client sent it): a 400 from
            # the error handlers, for the request without its headers.
            request = self._request_from_environ(environ, with_headers=False)
            error = exc
        response = self._respond_sync(
            request,
            environ["wsgi.input"].read,
            input_terminated=bool(environ.get("wsgi.input_terminated")),
            error=error,
        )
        status, headers, body = response.prepare(request)
        start_response(f"{status} {_reason(status)}", headers)
        if isinstance(body, bytes):
            return [body] if body else []
        # A file or any other iterable is handed to the server as it is;
        # WSGI servers call `close()` on it when they are done.
        return body

    def _bearings(
        self: "App", head: str, input: t.Any, listener: "Listener"
    ) -> "tuple[int, list[tuple[str, str]], t.Any]":
        """The app for `bearings.Server(app._bearings, raw=True)`.

        Bearings calls it on one of its worker threads with the request
        head it parsed, the body to read (`input`), and where it listens.
        It returns `(status, headers, body)`, which Bearings sends. Like
        `__call__`, without building a WSGI environ only to take it apart.
        """
        fields = head.split("\0")
        try:
            request = self._request_from_head(fields, listener)
            error = None
        except BadRequest as exc:
            # See `__call__`
            request = self._request_from_head(fields, listener, with_headers=False)
            error = exc
        response = self._respond_sync(request, input.read, error=error)
        return response.prepare(request)

    def _request_from_head(
        self, fields: "list[str]", listener: "Listener", *, with_headers: bool = True
    ) -> "Request":
        method, path, query, version, address, port = fields[:6]
        return self.request_cls(
            method=method,
            path=_path_from_head(path),
            query_string=query,
            headers=_headers_from_head(fields) if with_headers else None,
            scheme=listener.url_scheme,
            server=(listener.name, listener.port) if listener.name else None,
            client=(address, int(port) if port.isdigit() else None) if address else None,
            http_version=version.removeprefix("HTTP/"),
            server_software=listener.software,
            app=self,
        )

    def _request_from_environ(
        self, environ: dict, *, with_headers: bool = True
    ) -> "Request":
        # PEP 3333: the path comes as latin-1 "bytes in a str".
        path = environ.get("PATH_INFO", "") or "/"
        path = path.encode("latin-1", "replace").decode("utf-8", "replace")
        protocol = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        return self.request_cls(
            method=environ.get("REQUEST_METHOD", "GET"),
            path=path,
            query_string=environ.get("QUERY_STRING", ""),
            headers=_headers_from_environ(environ) if with_headers else (),
            scheme=environ.get("wsgi.url_scheme", "http"),
            server=_address(environ.get("SERVER_NAME"), environ.get("SERVER_PORT")),
            client=_address(environ.get("REMOTE_ADDR"), environ.get("REMOTE_PORT")),
            http_version=protocol.removeprefix("HTTP/"),
            server_software=environ.get("SERVER_SOFTWARE", ""),
            app=self,
        )

    def _respond_sync(
        self: "App",
        request: "Request",
        read: "Callable[[int], bytes]",
        *,
        input_terminated: bool = True,
        error: Exception | None = None,
    ) -> "Response":
        """`_respond`, on the calling thread, in a context of its own.

        The server runs many requests on each of its threads. Without a
        context per request, what one sets in `current` (the user, the
        session, the locale) would still be there for the next request on
        the same thread.

        `input_terminated` is the server's `wsgi.input_terminated`: whether
        `read()` returns `b""` at the end of the body (see
        `Request._read_body_sync`).

        `error`, if given, is the response's error from the start: the body
        is not read, and the error handlers answer.
        """
        return contextvars.copy_context().run(
            self._respond_sync_in_context,
            request,
            read,
            input_terminated=input_terminated,
            error=error,
        )

    def _respond_sync_in_context(
        self: "App",
        request: "Request",
        read: "Callable[[int], bytes]",
        *,
        input_terminated: bool = True,
        error: Exception | None = None,
    ) -> "Response":
        current.app = self
        current.request = request
        current.response = response = self.response_cls(self)
        if error is not None:
            response.error = error  # handled by the pipeline
        else:
            try:
                request._read_body_sync(read, input_terminated=input_terminated)
            except Exception as body_error:
                response.error = body_error  # handled by the pipeline
        response = self._run_pipeline(request, response)
        current.response = response
        return response
