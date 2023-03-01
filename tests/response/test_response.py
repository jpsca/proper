from datetime import datetime

from proper import DotDict, Request, Response


def test_set_etag():
    response = Response()

    response.fresh_when(etag=123, public=False)
    assert response.headers["ETag"] == 'W/"202cb962ac59075b964b07152d234b70"'
    assert response.headers["Cache-Control"] == "max-age=0, private, must-revalidate"

    response.fresh_when(etag=123, strong=True, public=True)
    assert response.headers["ETag"] == '"202cb962ac59075b964b07152d234b70"'
    assert response.headers["Cache-Control"] == "max-age=0, public, must-revalidate"

    response.fresh_when(etag=datetime(2020, 11, 24, 17, 17, 0))
    assert response.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'


def test_invalid_etag_value():
    response = Response()
    assert not response.fresh_when({})
    assert "ETag" not in response.headers


def test_fresh_when_from_objects():
    response = Response()

    obj = DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)})
    response.fresh_when(obj)
    assert response.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'
    assert response.headers["Last-Modified"] == "Tue, 24 Nov 2020 17:17:00 GMT"

    response.fresh_when([
        DotDict({"updated_at": datetime(2020, 5, 5)}),
        DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)}),
        DotDict({"updated_at": datetime(2020, 7, 28)}),
    ])
    assert response.headers["ETag"] == 'W/"77292437646103d054834b5a9f9cbf5d"'
    assert response.headers["Last-Modified"] == "Tue, 24 Nov 2020 17:17:00 GMT"


def test_is_fresh_by_etag():
    response = Response()

    response._request = Request(HTTP_IF_NONE_MATCH='W/"202cb962ac59075b964b07152d234b70"')
    assert response.fresh_when(etag=123)

    response._request = Request(HTTP_IF_NONE_MATCH='"abc", W/"202cb962ac59075b964b07152d234b70", W/"meh"')
    assert response.fresh_when(etag=123)

    response._request = Request(
        HTTP_IF_NONE_MATCH='W/"202cb962ac59075b964b07152d234b70"',
        HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT",
    )
    # If ETag match, Last-Modified is ignored
    assert response.fresh_when(etag=123, last_modified=datetime(2020, 11, 24, 17, 17, 0))

    response._request = Request(HTTP_IF_NONE_MATCH="")
    assert not response.fresh_when(etag=123)

    response._request = Request(HTTP_IF_NONE_MATCH='W/"abc"')
    assert not response.fresh_when(etag=123)

    response._request = None
    assert not response.fresh_when(etag=123)

    response._request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2020 07:28:00 GMT")
    assert response.fresh_when(last_modified=datetime(2019, 11, 24))

    response._request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT")
    assert not response.fresh_when(last_modified=datetime(2020, 11, 24))


# def test_set_dict_as_body():
#     response = Response()
#     response.body = {"i_am": "a json"}

#     assert response.body == '{"i_am": "a json"}'
#     assert response.content_type == "application/json"


# def test_set_list_as_body():
#     response = Response()
#     response.body = ["i_am", "also", "a json"]

#     assert response.body == '["i_am", "also", "a json"]'
#     assert response.content_type == "application/json"


# def test_non_renderable_become_string_when_set_as_body():
#     response = Response()
#     response.body = 5

#     assert response.body == "5"


# def test_encode_datetimes_in_json():
#     response = Response()
#     response.body = {"date": datetime(2022, 2, 23, 22, 42)}

#     assert response.body == '{"date": "2022-02-23T22:42:00"}'
#     assert response.content_type == "application/json"
