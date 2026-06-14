import typing as t
from urllib.parse import urlencode, urlparse

from ..types import TScope


__all__ = ("make_test_scope", )

SCHEME_DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}


def make_test_scope(
    url: str = "/",
    *,
    scope_type: str = "http",
    method: str = "GET",
    params: dict | None = None,
    **kw,
) -> TScope:
    upa = urlparse(url)
    scheme = upa.scheme or "http"
    path = upa.path or "/"

    if ":" in upa.netloc:
        host, port_str = upa.netloc.split(":")
        port = int(port_str)
    else:
        host = upa.netloc or "example.com"
        port = SCHEME_DEFAULT_PORTS.get(scheme, 80)

    if params:
        query_string = urlencode(params).encode()
    else:
        query_string = (upa.query or "").encode()

    headers: list[tuple[bytes, bytes]] = [
        (b"host", host.encode()),
    ]

    scope: dict[str, t.Any] = {
        "type": scope_type,
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "path": path,
        "query_string": query_string,
        "root_path": "",
        "scheme": scheme,
        "server": (host, port),
        "headers": headers,
    }

    for key, value in kw.items():
        if key == "headers":
            for name, val in value:
                headers.append((
                    name.encode() if isinstance(name, str) else name,
                    val.encode() if isinstance(val, str) else val,
                ))
        else:
            scope[key] = value

    return scope


def copy_file(
    stream: t.IO[bytes],
    target: t.IO[bytes],
    maxread: int = -1,
    buffer_size: int = 2 ** 16,
) -> int:
    """Read from *stream* and write to *target* until *maxread* or EOF."""
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)
