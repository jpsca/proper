import typing as t
from io import BytesIO
from urllib.parse import quote_plus, urlencode, urlparse
from wsgiref.util import setup_testing_defaults

from proper.helpers import tunnel_encode
from proper.types import TWSGIEnvironment


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
    env["wsgi.url_protocol"] = upa.scheme
    env["PATH_INFO"] = tunnel_encode(upa.path)

    if ":" in upa.netloc:
        host, port = upa.netloc.split(":")
    else:
        host, port = "example.com", "80"
    env["HTTP_HOST"] = host
    env["HTTP_PORT"] = port

    if params:
        query = quote_plus(urlencode(params))
    else:
        query = upa.query
    env["QUERY_STRING"] = query

    if body:
        if isinstance(body, dict):
            body = quote_plus(urlencode(body))
        elif isinstance(body, str):
            body = body.encode()
    env["wsgi.input"] = body

    env.update({key: str(value) for key, value in kw.items()})
    return env
