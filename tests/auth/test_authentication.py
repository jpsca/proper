"""The `Authentication` concern, with the auth addon's `User` and `Session`
models on an in-memory database."""
import pytest

from proper import current
from proper.concerns import CSRF_SESSION_KEY, Authentication
from proper.constants import AUTH_COOKIE_NAME
from proper.controller import Controller
from proper.core.response import Response
from proper.router import Route
from proper.test_client import make_test_request


CLIENT = ("203.0.113.5", 5000)


@pytest.fixture()
def Ctrl(app, models):
    class SessionController(Authentication, Controller):
        Session = models.Session

        def new(self):
            pass

        def index(self):
            pass

    app.router.add_route(
        Route(method="GET", path="/sign-in", to=SessionController.new, name="Session.new")
    )
    return SessionController


def _controller(app, Ctrl, *, cookie=None, action="index"):
    headers = [("cookie", cookie)] if cookie else []
    request = make_test_request("/private", app=app, client=CLIENT, headers=headers)
    request.matched_action = action
    return Ctrl(request, Response(app))


def _cookie_of(response):
    """The auth cookie the response set, as the next request sends it."""
    return f"{AUTH_COOKIE_NAME}={response.cookies[AUTH_COOKIE_NAME].coded_value}"


def test_new_session_for_signs_in(app, Ctrl, user):
    co = _controller(app, Ctrl)
    co.response.session = {CSRF_SESSION_KEY: "planted", "_redirect": "/x", "cart": [1]}

    session = co.new_session_for(user)

    assert current.auth_session == session
    assert current.user == user
    assert co.is_authenticated()
    assert session.ip_address == CLIENT[0]
    # A new CSRF token for the signed-in user; the rest of the session stays
    assert co.response.session == {"_redirect": "/x", "cart": [1]}
    assert co.response.cookies[AUTH_COOKIE_NAME]["httponly"]


def test_require_authentication_resumes_the_session_of_the_cookie(app, Ctrl, models, user):
    signed = _controller(app, Ctrl)
    session = signed.new_session_for(user)
    current.auth_session = current.user = None

    co = _controller(app, Ctrl, cookie=_cookie_of(signed.response))
    co.require_authentication()

    assert current.auth_session.id == session.id
    assert co.response.location is None
    # once authenticated, there is nothing else to do
    co.require_authentication()


def test_require_authentication_without_a_session(app, Ctrl):
    co = _controller(app, Ctrl)
    co.require_authentication()
    assert co.response.location == "/sign-in"
    assert co.response.session["_redirect"] == "/private"


@pytest.mark.parametrize("skip", [True, ["index"]])
def test_skip_authentication(app, Ctrl, skip):
    Ctrl.skip_authentication = skip
    co = _controller(app, Ctrl)
    co.require_authentication()
    assert co.response.location is None


def test_skip_authentication_with_one_name(app, Ctrl):
    Ctrl.skip_authentication = "index"
    co = _controller(app, Ctrl)
    co.require_authentication()
    assert co.response.location is None

    co = _controller(app, Ctrl, action="in")
    co.require_authentication()
    assert co.response.location == "/sign-in"


def test_skip_authentication_for_other_actions(app, Ctrl):
    Ctrl.skip_authentication = False
    co = _controller(app, Ctrl)
    co.require_authentication()
    assert co.response.location == "/sign-in"


def test_terminate_session(app, Ctrl, models, user):
    co = _controller(app, Ctrl)
    session = co.new_session_for(user)
    co.response.session["cart"] = [1]

    co.terminate_session()

    assert models.Session.get_or_none(models.Session.id == session.id) is None
    assert current.auth_session is None and current.user is None
    assert co.response.session == {}
    assert co.response.cookies[AUTH_COOKIE_NAME]["max-age"] == 0

    current.user = user
    co.terminate_session()  # without a session
    assert current.user is None


def test_redirect_if_authenticated(app, Ctrl, user):
    co = _controller(app, Ctrl)
    co.redirect_if_authenticated()
    assert co.response.location is None

    signed = _controller(app, Ctrl)
    signed.new_session_for(user)
    current.auth_session = current.user = None
    co = _controller(app, Ctrl, cookie=_cookie_of(signed.response))
    co.response.session["_redirect"] = "/back"
    co.redirect_if_authenticated(flash="Welcome")
    assert co.response.location == "/back"
    assert "_redirect" not in co.response.session


def test_redirect_if_already_authenticated(app, Ctrl, user):
    co = _controller(app, Ctrl)
    co.new_session_for(user)
    co.redirect_if_authenticated()
    assert co.response.location == "/"


def test_redirect_after_authentication_defaults(app, Ctrl):
    co = _controller(app, Ctrl)
    co.redirect_after_authentication(default="/home")
    assert co.response.location == "/home"
