import pytest

from proper import Request, Response
from proper.constants import GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
from proper.iplugs.method_override import method_override


@pytest.mark.parametrize("_method", [PUT, PATCH, DELETE])
def test_method_override(_method):
    req = Request(method=POST, path="/?_method=" + _method)
    resp = Response()
    method_override(req, resp, None)

    assert req.method == _method
    assert req.real_method == POST


@pytest.mark.parametrize("_method", [GET, HEAD, OPTIONS, "MEH"])
def test_ignore_invalid_new_methods(_method):
    req = Request(method=POST, path="/?_method=" + _method)
    resp = Response()
    method_override(req, resp, None)

    assert req.method == POST


@pytest.mark.parametrize("_method", [GET, PUT, PATCH, DELETE, HEAD, OPTIONS, "MEH"])
def test_only_override_post(_method):
    _m = PUT if _method != PUT else PATCH
    req = Request(method=_method, path="/?_method=" + _m)
    resp = Response()
    method_override(req, resp, None)

    assert req.method == _method
