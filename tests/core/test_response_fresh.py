from datetime import datetime, timezone

from proper import DotDict, Request, Response
from proper import status as pstatus
from proper.global_context import current
from proper.helpers.asgi import make_test_scope


def _make_request(**headers):
    """Build a Request with custom headers."""
    header_list = []
    for name, val in headers.items():
        header_list.append((name, val))
    scope = make_test_scope(headers=header_list)
    request = Request(scope)
    return request


def _make_response(*, status=pstatus.ok, **scope_kw):
    """Build a Response with a valid ASGI scope."""
    scope = make_test_scope(**scope_kw)
    response = Response(scope, status=status)
    return response



class TestFreshWhen:
    def test_set_etag_weak(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, public=False, request=req)
        assert resp.etag and resp.etag.startswith('W/"')
        assert resp.cache_control == ["max-age=0", "private", "must-revalidate"]

    def test_set_etag_strong_public(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, strong=True, public=True, request=req)
        assert resp.etag and resp.etag.startswith('"')
        assert not resp.etag.startswith("W/")
        assert resp.cache_control == ["max-age=0", "public", "must-revalidate"]

    def test_set_etag_from_datetime(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=datetime(2020, 11, 24, 17, 17, 0), request=req)
        assert resp.etag is not None

    def test_from_single_object(self):
        req = _make_request()
        resp = _make_response()
        obj = DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)})
        resp.fresh_when(obj, request=req)
        assert resp.etag is not None
        assert resp.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)

    def test_from_list_of_objects(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when([
            DotDict({"updated_at": datetime(2020, 5, 5)}),
            DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)}),
            DotDict({"updated_at": datetime(2020, 7, 28)}),
        ], request=req)
        assert resp.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)

    def test_from_objects_with_none_filtered(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when([
            None,
            DotDict({"updated_at": datetime(2020, 1, 1)}),
        ], request=req)
        assert resp.etag is not None

    def test_empty_iterable_no_etag(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when([], request=req)
        assert resp.etag is None

    def test_all_none_objects(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when([None, None], request=req)
        assert resp.etag is None

    def test_invalid_etag_value(self):
        req = _make_request()
        resp = _make_response()
        assert not resp.fresh_when({}, request=req)
        assert resp.etag is None


class TestIsFresh:
    def test_no_request(self):
        current.request = _make_request()
        resp = _make_response()
        assert resp.is_fresh(request=None) is False

    def test_no_request_no_current(self):
        current.request = None  # type: ignore
        resp = _make_response()
        assert resp.is_fresh() is False

    def test_etag_match(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, request=req)
        request = _make_request(**{"if-none-match": resp.etag})
        assert resp.is_fresh(request=request) is True

    def test_etag_no_match(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, request=req)
        request = _make_request(**{"if-none-match": 'W/"abc"'})
        assert resp.is_fresh(request=request) is False

    def test_last_modified_fresh(self):
        resp = _make_response()
        resp.set_last_modified(datetime(2019, 1, 1))
        resp.set_etag(None)
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is True

    def test_last_modified_stale(self):
        resp = _make_response()
        resp.set_last_modified(datetime(2020, 11, 24))
        resp.set_etag(None)
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2015 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is False

    def test_etag_takes_priority_over_last_modified(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, request=req)
        request = _make_request(
            **{
                "if-none-match": resp.etag,
                "if-modified-since": "Wed, 21 Oct 2015 07:28:00 GMT",
            }
        )
        assert resp.is_fresh(request=request) is True

    def test_empty_if_none_match(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, request=req)
        request = _make_request(**{"if-none-match": ""})
        assert resp.is_fresh(request=request) is False

    def test_uses_current_request_fallback(self):
        req = _make_request()
        resp = _make_response()
        resp.fresh_when(etag=123, request=req)
        request = _make_request(**{"if-none-match": resp.etag})
        current.request = request
        assert resp.is_fresh() is True

