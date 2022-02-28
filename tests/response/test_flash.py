from proper import Dot, Response
from proper.constants import FLASHES_SESSION_KEY


def test_flash():
    resp = Response()
    resp._session = Dot({})
    resp.flash["notice"] = "Welcome back!"

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"notice": "Welcome back!"}


def test_flash_alert():
    resp = Response()
    resp._session = Dot({})
    msg = "Is the final countdown"
    resp.flash.alert(msg)

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"alert": msg}


def test_flash_notice():
    resp = Response()
    resp._session = Dot({})
    msg = "This was a triumph"
    resp.flash.notice(msg)

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"notice": msg}


def test_flash_error():
    resp = Response()
    resp._session = Dot({})
    msg = "Huge mistake"
    resp.flash.error(msg)

    flashes = resp.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"error": msg}
