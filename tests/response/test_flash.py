from proper import DotDict, Response
from proper.constants import FLASHES_SESSION_KEY


def test_flash():
    response = Response()
    response._session = DotDict({})
    response.flash["notice"] = "Welcome back!"

    flashes = response.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"notice": "Welcome back!"}


def test_flash_alert():
    response = Response()
    response._session = DotDict({})
    msg = "Is the final countdown"
    response.flash.alert(msg)

    flashes = response.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"alert": msg}


def test_flash_notice():
    response = Response()
    response._session = DotDict({})
    msg = "This was a triumph"
    response.flash.notice(msg)

    flashes = response.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"notice": msg}


def test_flash_error():
    response = Response()
    response._session = DotDict({})
    msg = "Huge mistake"
    response.flash.error(msg)

    flashes = response.session.get(FLASHES_SESSION_KEY)
    assert flashes == {"error": msg}
