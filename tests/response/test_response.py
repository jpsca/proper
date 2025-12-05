from datetime import datetime, timezone

from proper import DotDict, Request, Response
from proper.constants import FLASHES_SESSION_KEY


def test_set_etag():
    response = Response()

    response.fresh_when(etag=123, public=False)
    assert response.etag == 'W/"40bd001563085fc35165329ea1ff5c5ecbdbbeef"'
    assert response.cache_control == ["max-age=0", "private", "must-revalidate"]

    response.fresh_when(etag=123, strong=True, public=True)
    assert response.etag == '"40bd001563085fc35165329ea1ff5c5ecbdbbeef"'
    assert response.cache_control == ["max-age=0", "public", "must-revalidate"]

    response.fresh_when(etag=datetime(2020, 11, 24, 17, 17, 0))
    assert response.etag == 'W/"d55c52d5e5e906167b75eb6fbf36b22e41e17222"'


def test_invalid_etag_value():
    response = Response()
    assert not response.fresh_when({})
    assert response.etag is None


def test_fresh_when_from_objects():
    response = Response()

    obj = DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)})
    response.fresh_when(obj)
    assert response.etag == 'W/"d55c52d5e5e906167b75eb6fbf36b22e41e17222"'
    assert response.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)

    response.fresh_when(
        [
            DotDict({"updated_at": datetime(2020, 5, 5)}),
            DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)}),
            DotDict({"updated_at": datetime(2020, 7, 28)}),
        ]
    )
    assert response.etag == 'W/"d55c52d5e5e906167b75eb6fbf36b22e41e17222"'
    assert response.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)


def test_is_fresh_by_etag():
    response = Response()

    request = Request(
        HTTP_IF_NONE_MATCH='W/"40bd001563085fc35165329ea1ff5c5ecbdbbeef"'
    )
    assert response.fresh_when(etag=123, request=request)

    request = Request(
        HTTP_IF_NONE_MATCH='"abc", W/"40bd001563085fc35165329ea1ff5c5ecbdbbeef", W/"meh"'
    )
    assert response.fresh_when(etag=123, request=request)

    request = Request(
        HTTP_IF_NONE_MATCH='W/"40bd001563085fc35165329ea1ff5c5ecbdbbeef"',
        HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT",
    )
    # If ETag match, Last-Modified is ignored
    assert response.fresh_when(
        etag=123, last_modified=datetime(2020, 11, 24, 17, 17, 0), request=request
    )

    request = Request(HTTP_IF_NONE_MATCH="")
    assert not response.fresh_when(etag=123, request=request)

    request = Request(HTTP_IF_NONE_MATCH='W/"abc"')
    assert not response.fresh_when(etag=123, request=request)

    request = None
    assert not response.fresh_when(etag=123, request=request)

    request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2020 07:28:00 GMT")
    assert response.fresh_when(last_modified=datetime(2019, 11, 24), request=request)

    request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT")
    assert not response.fresh_when(last_modified=datetime(2020, 11, 24), request=request)


def test_flash():
    response = Response()
    response.flash.message("info", "Welcome back!")

    flashes = response.session.get(FLASHES_SESSION_KEY)
    assert flashes == [("info", "Welcome back!")]

