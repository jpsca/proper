from datetime import datetime

from proper import Dot, Request, Response
from proper.response import FLASHES_SESSION_KEY


def test_flash():
    resp = Response()
    resp._session = Dot({})
    resp.flash("Welcome back!")

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == [("Welcome back!", {})]


def test_flash_with_data():
    resp = Response()
    resp._session = Dot({})
    resp.flash("LOGGED_IN", cat="success", path="/myprofile")

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == [("LOGGED_IN", {"cat": "success", "path": "/myprofile"})]


def test_multiple_flashes():
    resp = Response()
    resp._session = Dot({})
    resp.flash("flash1")
    resp.flash("flash2")

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == [("flash1", {}), ("flash2", {})]


def test_set_etag():
    resp = Response()

    resp.fresh_when(etag=123, public=False)
    assert resp.headers["ETag"] == 'W/"202cb962ac59075b964b07152d234b70"'
    assert resp.headers["Cache-Control"] == "max-age=0, private, must-revalidate"

    resp.fresh_when(etag=123, strong=True, public=True)
    assert resp.headers["ETag"] == '"202cb962ac59075b964b07152d234b70"'
    assert resp.headers["Cache-Control"] == "max-age=0, public, must-revalidate"

    resp.fresh_when(etag=datetime(2020, 11, 24, 17, 17, 0))
    assert resp.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'


def test_invalid_etag_value():
    resp = Response()
    assert not resp.fresh_when({})
    assert "ETag" not in resp.headers


def test_fresh_when_from_objects():
    resp = Response()

    obj = Dot({"updated_at": datetime(2020, 11, 24, 17, 17, 0)})
    resp.fresh_when(obj)
    assert resp.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'
    assert resp.headers["Last-Modified"] == "Tue, 24 Nov 2020 17:17:00 GMT"

    resp.fresh_when([
        Dot({"updated_at": datetime(2020, 5, 5)}),
        Dot({"updated_at": datetime(2020, 11, 24, 17, 17, 0)}),
        Dot({"updated_at": datetime(2020, 7, 28)}),
    ])
    assert resp.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'
    assert resp.headers["Last-Modified"] == "Tue, 24 Nov 2020 17:17:00 GMT"


def test_is_fresh_by_etag():
    resp = Response()

    resp._req = Request(HTTP_IF_NONE_MATCH='W/"202cb962ac59075b964b07152d234b70"')
    assert resp.fresh_when(etag=123)

    resp._req = Request(HTTP_IF_NONE_MATCH='"abc", W/"202cb962ac59075b964b07152d234b70", W/"meh"')
    assert resp.fresh_when(etag=123)

    resp._req = Request(
        HTTP_IF_NONE_MATCH='W/"202cb962ac59075b964b07152d234b70"',
        HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT",
    )
    # If ETag match, Last-Modified is ignored
    assert resp.fresh_when(etag=123, last_modified=datetime(2020, 11, 24, 17, 17, 0))

    resp._req = Request(HTTP_IF_NONE_MATCH="")
    assert not resp.fresh_when(etag=123)

    resp._req = Request(HTTP_IF_NONE_MATCH='W/"abc"')
    assert not resp.fresh_when(etag=123)

    resp._req = None
    assert not resp.fresh_when(etag=123)

    resp._req = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2020 07:28:00 GMT")
    assert resp.fresh_when(last_modified=datetime(2019, 11, 24))

    resp._req = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT")
    assert not resp.fresh_when(last_modified=datetime(2020, 11, 24))
