"""WSGI: the sync face of the app.

The server calls `app(environ, start_response)` on one of its own threads, so
the pipeline runs right there: no event loop, no hand-off to a worker. This is
the fast path for HTTP; WebSockets need RSGI (see `app_ws.py`).
"""
import typing as t
from http import HTTPStatus

from ..global_context import current


if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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


class AppWsgi:
    """A mixin that makes the app a WSGI callable."""

    config: t.Any
    request_cls: t.Any
    response_cls: t.Any

    def __call__(
        self, environ: dict, start_response: "Callable"
    ) -> "Iterable[bytes]":
        request = self._request_from_environ(environ)
        response = self._respond_sync(request, environ["wsgi.input"].read)
        status, headers, body = response.prepare(request)
        start_response(f"{status} {_reason(status)}", headers)
        if isinstance(body, bytes):
            return [body] if body else []
        # A file or any other iterable is handed to the server as it is;
        # WSGI servers call `close()` on it when they are done.
        return body

    def _request_from_environ(self, environ: dict) -> "Request":
        # PEP 3333: the path comes as latin-1 "bytes in a str".
        path = environ.get("PATH_INFO", "") or "/"
        path = path.encode("latin-1", "replace").decode("utf-8", "replace")
        protocol = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        return self.request_cls(
            method=environ.get("REQUEST_METHOD", "GET"),
            path=path,
            query_string=environ.get("QUERY_STRING", ""),
            headers=_headers_from_environ(environ),
            scheme=environ.get("wsgi.url_scheme", "http"),
            server=_address(environ.get("SERVER_NAME"), environ.get("SERVER_PORT")),
            client=_address(environ.get("REMOTE_ADDR"), environ.get("REMOTE_PORT")),
            http_version=protocol.removeprefix("HTTP/"),
            app=self,
        )

    def _respond_sync(
        self, request: "Request", read: "Callable[[int], bytes]"
    ) -> "Response":
        """`_respond`, on the calling thread."""
        current.app = self
        current.request = request
        current.response = response = self.response_cls(self)
        try:
            request._read_body_sync(read)
        except Exception as error:
            response.error = error  # handled by the pipeline
        response = self._run_pipeline(request, response)  # type: ignore[attr-defined]
        current.response = response
        return response
