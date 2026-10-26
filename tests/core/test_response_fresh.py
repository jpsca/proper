from datetime import datetime, timezone

import pytest

from proper import DotDict, Response
from proper import status as pstatus
from proper.global_context import current
from proper.test_client import make_test_request


def _make_request(**headers):
    """Build a Request with custom headers."""
    header_list = []
    for name, val in headers.items():
        header_list.append((name, val))
    request = make_test_request(headers=header_list)
    return request


def _make_response(*, status=pstatus.ok, app=None):
    response = Response(app, status=status)
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


class TestIsFreshLastModified:
    def test_fractional_seconds(self):
        """HTTP dates have whole seconds, so the client sends back the
        Last-Modified without its fraction."""
        resp = _make_response()
        resp.set_last_modified(datetime(2020, 10, 21, 7, 28, 0, 500_000))
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is True

    def test_fractional_seconds_from_timestamp(self):
        resp = _make_response()
        resp.set_last_modified(1603265280.75)  # 2020-10-21 07:28:00.75 UTC
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is True

    def test_one_second_later_is_stale(self):
        resp = _make_response()
        resp.set_last_modified(datetime(2020, 10, 21, 7, 28, 1))
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is False

    @pytest.mark.parametrize(
        "value",
        [
            "garbage",
            "Sun, 99 Nov 1994 08:49:37 GMT",
            # The offset moves it past year 9999.
            "Fri, 31 Dec 9999 23:59:59 -0100",
        ],
    )
    def test_invalid_date_is_ignored(self, value):
        """RFC 9110 §13.1.3: an invalid date is ignored, not a 500."""
        req = _make_request(**{"if-modified-since": value})
        resp = _make_response()
        resp.set_last_modified(datetime(2020, 1, 1))
        assert resp.is_fresh(request=req) is False


class TestIsFreshIfNoneMatch:
    def test_weak_request_tag_matches_strong_etag(self):
        resp = _make_response()
        resp.set_etag(123, strong=True)
        assert resp.etag
        request = _make_request(**{"if-none-match": f"W/{resp.etag}"})
        assert resp.is_fresh(request=request) is True

    def test_strong_request_tag_matches_weak_etag(self):
        resp = _make_response()
        resp.set_etag(123)
        assert resp.etag
        request = _make_request(**{"if-none-match": resp.etag.removeprefix("W/")})
        assert resp.is_fresh(request=request) is True

    def test_match_in_list(self):
        resp = _make_response()
        resp.set_etag(123)
        request = _make_request(**{"if-none-match": f'"abc", {resp.etag}, W/"def"'})
        assert resp.is_fresh(request=request) is True

    def test_star_matches_any_etag(self):
        resp = _make_response()
        resp.set_etag(123)
        request = _make_request(**{"if-none-match": "*"})
        assert resp.is_fresh(request=request) is True

    def test_star_without_etag(self):
        """RFC 9110 §13.1.2: `*` matches whenever the resource has a current
        representation, which a 2xx response to a GET or HEAD is."""
        resp = _make_response()
        request = _make_request(**{"if-none-match": "*"})
        assert resp.is_fresh(request=request) is True

    def test_star_without_etag_ignores_if_modified_since(self):
        resp = _make_response()
        resp.set_last_modified(datetime(2021, 1, 1))
        request = _make_request(
            **{
                "if-none-match": "*",
                "if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT",
            }
        )
        assert resp.is_fresh(request=request) is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    def test_star_is_not_fresh_for_other_methods(self, method):
        resp = _make_response()
        request = make_test_request(method=method, headers=[("if-none-match", "*")])
        assert resp.is_fresh(request=request) is False

    @pytest.mark.parametrize("status", [pstatus.see_other, pstatus.not_found])
    def test_star_is_not_fresh_for_other_statuses(self, status):
        resp = _make_response(status=status)
        request = _make_request(**{"if-none-match": "*"})
        assert resp.is_fresh(request=request) is False

    def test_if_modified_since_ignored_when_etag_differs(self):
        resp = _make_response()
        resp.set_etag(123)
        resp.set_last_modified(datetime(2019, 1, 1))
        request = _make_request(
            **{
                "if-none-match": 'W/"abc"',
                "if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT",
            }
        )
        assert resp.is_fresh(request=request) is False

    def test_if_modified_since_ignored_without_etag(self):
        resp = _make_response()
        resp.set_last_modified(datetime(2019, 1, 1))
        request = _make_request(
            **{
                "if-none-match": 'W/"abc"',
                "if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT",
            }
        )
        assert resp.is_fresh(request=request) is False


class TestIsFreshMethodAndStatus:
    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    def test_fresh_for_get_and_head(self, method):
        resp = _make_response()
        resp.set_etag(123)
        request = make_test_request(method=method, headers=[("if-none-match", resp.etag)])
        assert resp.is_fresh(request=request) is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_not_fresh_for_other_methods(self, method):
        resp = _make_response()
        resp.set_etag(123)
        resp.set_last_modified(datetime(2019, 1, 1))
        request = make_test_request(
            method=method,
            headers=[
                ("if-none-match", resp.etag),
                ("if-modified-since", "Wed, 21 Oct 2020 07:28:00 GMT"),
            ],
        )
        assert resp.is_fresh(request=request) is False

    @pytest.mark.parametrize("status", [pstatus.created, pstatus.no_content])
    def test_fresh_for_2xx(self, status):
        resp = _make_response(status=status)
        resp.set_etag(123)
        request = _make_request(**{"if-none-match": resp.etag})
        assert resp.is_fresh(request=request) is True

    @pytest.mark.parametrize(
        "status",
        [
            pstatus.see_other,
            pstatus.not_modified,
            pstatus.not_found,
            pstatus.server_error,
        ],
    )
    def test_not_fresh_for_other_statuses(self, status):
        resp = _make_response(status=status)
        resp.set_etag(123)
        resp.set_last_modified(datetime(2019, 1, 1))
        request = _make_request(**{"if-none-match": resp.etag})
        assert resp.is_fresh(request=request) is False
        request = _make_request(**{"if-modified-since": "Wed, 21 Oct 2020 07:28:00 GMT"})
        assert resp.is_fresh(request=request) is False

    def test_fresh_when_returns_false_for_post(self):
        resp = _make_response()
        resp.set_etag("abc")
        request = make_test_request(method="POST", headers=[("if-none-match", resp.etag)])
        assert resp.fresh_when(etag="abc", request=request) is False
