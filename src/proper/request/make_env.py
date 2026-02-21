import typing as t
from io import BytesIO
from urllib.parse import urlencode, urlparse
from wsgiref.util import setup_testing_defaults

from ..helpers import tunnel_encode
from ..types import TWSGIEnvironment


__all__ = ("make_test_env", )


def make_test_env(
    url: str = "/",
    *,
    params: dict | None = None,
    body: dict | str | bytes | BytesIO = b"",
    **kw,
) -> TWSGIEnvironment:
    env: dict[str, t.Any] = {
        "REMOTE_ADDR": "127.0.0.1",
    }
    setup_testing_defaults(env)

    upa = urlparse(url)
    env["wsgi.url_protocol"] = upa.scheme or "http"
    env["PATH_INFO"] = tunnel_encode(upa.path)

    if ":" in upa.netloc:
        host, port = upa.netloc.split(":")
    else:
        host, port = "example.com", "80"
    env["HTTP_HOST"] = host
    env["HTTP_PORT"] = port

    if params:
        query = urlencode(params)
    else:
        query = upa.query
    env["QUERY_STRING"] = query

    if body:
        if isinstance(body, dict):
            body = urlencode(body).encode()
        elif isinstance(body, str):
            body = body.encode()
    if not isinstance(body, BytesIO):
        body = BytesIO(body)
    env["wsgi.input"] = body

    env.update({key: str(value) for key, value in kw.items()})
    return env
