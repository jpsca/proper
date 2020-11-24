from datetime import datetime

from proper.response import FLASHES_SESSION_KEY, Response
from proper.helpers import Dot


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

    resp.fresh_when(123)
    assert resp.headers["Etag"] == ''

    resp.fresh_when(datetime(2020, 11, 24, 17, 17, 0))
    assert resp.headers["Etag"] == ''


def test_set_strong_etag():
    resp = Response()

    resp.fresh_when(123, strong=True)
    assert resp.headers["Etag"] == ''
