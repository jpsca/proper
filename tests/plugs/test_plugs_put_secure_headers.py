from proper import plugs
from proper import Request
from proper import Response


def test_put_secure_headers():
    req = Request()
    resp = Response()
    resp.dispatched = True
    plugs.put_secure_headers(req, resp, None)

    for key in (
        "x-frame-options",
        "x-xss-protection",
        "x-content-type-options",
        "x-download-options",
        "x-permitted-cross-domain-policies",
        "cross-origin-window-policy",
    ):
        assert key in resp.headers


def test_dont_put_secure_headers_before_dispatching():
    req = Request()
    resp = Response()
    plugs.put_secure_headers(req, resp, None)

    assert "x-frame-options" not in resp.headers
