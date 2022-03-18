import pytest

from proper import Request, Response
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
from proper.middleware import method_override


@pytest.mark.parametrize("_method", [PUT, PATCH, DELETE])
def test_method_override(_method):
    req = Request(REQUEST_METHOD=POST, QUERY_STRING="_method=" + _method)
    resp = Response()
    method_override(req, resp, None)

    assert req.method == _method
    assert req.request_method == POST


@pytest.mark.parametrize("_method", [GET, HEAD, OPTIONS, "MEH"])
def test_ignore_invalid_new_methods(_method):
    req = Request(REQUEST_METHOD=POST, QUERY_STRING="_method=" + _method)
    resp = Response()
    method_override(req, resp, None)

    assert req.request_method == POST


@pytest.mark.parametrize("_method", [GET, PUT, PATCH, DELETE, HEAD, OPTIONS, "MEH"])
def test_only_override_post(_method):
    _m = PUT if _method != PUT else PATCH
    req = Request(REQUEST_METHOD=_method, QUERY_STRING="_method=" + _m)
    resp = Response()
    method_override(req, resp, None)

    assert req.request_method == _method
