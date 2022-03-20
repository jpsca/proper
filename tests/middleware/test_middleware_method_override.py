import pytest

from proper import Request, Response
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
from proper.middleware import method_override


@pytest.mark.parametrize("_method", [PUT, PATCH, DELETE])
def test_method_override(_method):
    request = Request(REQUEST_METHOD=POST, QUERY_STRING="_method=" + _method)
    response = Response()
    method_override(request, response, None)

    assert request.method == _method
    assert request.request_method == POST


@pytest.mark.parametrize("_method", [GET, HEAD, OPTIONS, "MEH"])
def test_ignore_invalid_new_methods(_method):
    request = Request(REQUEST_METHOD=POST, QUERY_STRING="_method=" + _method)
    response = Response()
    method_override(request, response, None)

    assert request.request_method == POST


@pytest.mark.parametrize("_method", [GET, PUT, PATCH, DELETE, HEAD, OPTIONS, "MEH"])
def test_only_override_post(_method):
    _m = PUT if _method != PUT else PATCH
    request = Request(REQUEST_METHOD=_method, QUERY_STRING="_method=" + _m)
    response = Response()
    method_override(request, response, None)

    assert request.request_method == _method
