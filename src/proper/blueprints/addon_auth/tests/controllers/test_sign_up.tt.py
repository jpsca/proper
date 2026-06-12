import pytest

from [[app_name]].forms.auth import validators
from [[app_name]].main import app
from [[app_name]].models import Session, User


# A strong password (>= AUTH_PASSWORD_MINLEN)
GOOD_PASSWORD = "zx7-Qw9-mlp2-kte"
# A well-known breached password (>= AUTH_PASSWORD_MINLEN)
BAD_PASSWORD = "password123"


@pytest.fixture(autouse=True)
def stub_pwned_api(request, monkeypatch):
    """Stub the "Have I been pwned?" API so tests stay fast and offline.

    A test can request the `real_pwned_api` fixture to opt out and hit the
    real API instead.
    """
    if "real_pwned_api" in request.fixturenames:
        return
    monkeypatch.setattr(validators, "get_pwned_count", lambda *args, **kwargs: 0)


@pytest.fixture()
def real_pwned_api():
    """Opt out of `stub_pwned_api` to exercise the real "Have I been pwned?" API."""


# ----


def test_new_renders_sign_up_page(client):
    response = client.get(app.url_for("SignUp.new"))
    assert response.status == 200


def test_new_redirects_when_already_authenticated(signed_client):
    response = signed_client.get(app.url_for("SignUp.new"))
    assert response.status == 303


def test_create_signs_up_with_valid_data(client):
    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "alice",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        },
    )

    assert response.status == 303
    assert response.headers["location"] == "/"

    user = User.get_by_login("alice")
    assert user is not None
    assert Session.select().where(Session.user == user).count() == 1


def test_create_normalizes_the_login(client):
    # Uppercase and surrounding whitespace must be normalized before storing.
    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "  ALICE  ",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        },
    )

    assert response.status == 303
    assert User.get_by_login("alice") is not None


def test_create_with_taken_login_does_not_sign_up(client):
    User.create(login="bob", password=GOOD_PASSWORD)

    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "bob",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        },
    )

    assert response.status == 422
    assert User.select().where(User.login == "bob").count() == 1
    assert Session.select().count() == 0


def test_create_with_short_password_does_not_sign_up(client):
    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "carol",
            "password1": "short",
            "password2": "short",
        },
    )

    assert response.status == 422
    assert User.get_by_login("carol") is None
    assert Session.select().count() == 0


def test_create_with_pwned_password_does_not_sign_up(client, monkeypatch):
    monkeypatch.setattr(
        validators,
        "get_pwned_count",
        lambda *args, **kwargs: 5
    )

    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "dave",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        },
    )

    assert response.status == 422
    assert User.get_by_login("dave") is None
    assert Session.select().count() == 0


def test_create_with_mismatched_passwords_does_not_sign_up(client):
    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "erin",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD + "-different",
        },
    )

    assert response.status == 422
    assert User.get_by_login("erin") is None
    assert Session.select().count() == 0


def test_create_with_blank_fields_does_not_sign_up(client):
    response = client.post(
        app.url_for("SignUp.create"),
        body={"login": "", "password1": "", "password2": ""},
    )

    assert response.status == 422
    assert Session.select().count() == 0


def test_create_with_breached_password_uses_real_api(client, real_pwned_api):
    # No stub here: this exercises the real `get_pwned_count`. "password123" is
    # a well-known breached password, rejected whether the API is reachable
    # (live lookup) or not (local fallback list).
    response = client.post(
        app.url_for("SignUp.create"),
        body={
            "login": "frank",
            "password1": BAD_PASSWORD,
            "password2": BAD_PASSWORD,
        },
    )

    assert response.status == 422
    assert User.get_by_login("frank") is None
    assert Session.select().count() == 0
