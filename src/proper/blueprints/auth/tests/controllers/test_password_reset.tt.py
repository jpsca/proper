import pytest

from [[app_name]].forms.auth import validators
from [[app_name]].main import app
from [[app_name]].models import Session, User


# A strong password (>= AUTH_PASSWORD_MINLEN)
GOOD_PASSWORD = "zx7-Qw9-mlp2-kte"
NEW_PASSWORD = "NewPass-9xkqz7"


@pytest.fixture(autouse=True)
def stub_pwned_api(request, monkeypatch):
    """Stub the "Have I been pwned?" API so tests stay fast and offline.

    A test can request the `real_pwned_api` fixture to opt out and hit the
    real API instead.
    """
    monkeypatch.setattr(validators, "get_pwned_count", lambda *args, **kwargs: 0)


@pytest.fixture(autouse=True)
def clear_outbox():
    """The in-memory outbox persists across tests, so reset it each time."""
    app.mailer.outbox.clear()


# ----


def reset_token_for(user):
    return user.generate_token_for("password_reset")


def test_new_renders_request_page(client):
    response = client.get(app.url_for("PasswordReset.new"))
    assert response.status == 200


def test_new_redirects_when_already_authenticated(signed_client):
    response = signed_client.get(app.url_for("PasswordReset.new"))
    assert response.status == 303


def test_create_with_valid_login_sends_email_and_redirects(client):
    User.create(login="alice", password=GOOD_PASSWORD)

    response = client.post(
        app.url_for("PasswordReset.create"),
        body={"login": "alice"},
    )

    assert response.status == 303
    assert response.headers["location"] == "/password-reset/sent"

    assert len(app.mailer.outbox) == 1
    message = app.mailer.outbox[-1]
    assert message["To"] == "alice"
    assert message["Subject"] == "Reset your password"


def test_create_with_unknown_login_redisplays_form(client):
    response = client.post(
        app.url_for("PasswordReset.create"),
        body={"login": "nobody"},
    )

    assert response.status == 422
    assert app.mailer.outbox == []


def test_create_with_blank_login_redisplays_form(client):
    response = client.post(
        app.url_for("PasswordReset.create"),
        body={"login": ""},
    )

    assert response.status == 422


def test_show_renders_sent_confirmation(client):
    response = client.get(app.url_for("PasswordReset.show", token="sent"))
    assert response.status == 200


def test_edit_with_valid_token_renders_form(client):
    user = User.create(login="bob", password=GOOD_PASSWORD)

    response = client.get(
        app.url_for("PasswordReset.edit", token=reset_token_for(user))
    )

    assert response.status == 200


def test_edit_with_invalid_token_shows_invalid_page(client):
    response = client.get(app.url_for("PasswordReset.edit", token="bogus"))
    assert response.status == 200


def test_update_with_valid_token_changes_password_and_signs_in(client):
    user = User.create(login="carol", password=GOOD_PASSWORD)

    response = client.patch(
        app.url_for("PasswordReset.update", token=reset_token_for(user)),
        body={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
    )

    assert response.status == 303
    assert response.headers["location"] == "/"
    assert User.authenticate(login="carol", password=NEW_PASSWORD) is not None
    assert Session.select().where(Session.user == user).count() == 1


def test_update_with_short_password_redisplays_form(client):
    user = User.create(login="dave", password=GOOD_PASSWORD)

    response = client.patch(
        app.url_for("PasswordReset.update", token=reset_token_for(user)),
        body={"password1": "short", "password2": "short"},
    )

    assert response.status == 422
    assert User.authenticate(login="dave", password="short") is None


def test_update_with_pwned_password_redisplays_form(client, monkeypatch):
    monkeypatch.setattr(validators, "get_pwned_count", lambda *args, **kwargs: 5)
    user = User.create(login="erin", password=GOOD_PASSWORD)

    response = client.patch(
        app.url_for("PasswordReset.update", token=reset_token_for(user)),
        body={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
    )

    assert response.status == 422
    assert User.authenticate(login="erin", password=NEW_PASSWORD) is None


def test_update_with_mismatched_passwords_redisplays_form(client):
    user = User.create(login="frank", password=GOOD_PASSWORD)

    response = client.patch(
        app.url_for("PasswordReset.update", token=reset_token_for(user)),
        body={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD + "-different"},
    )

    assert response.status == 422
    assert User.authenticate(login="frank", password=NEW_PASSWORD) is None


def test_update_with_invalid_token_shows_invalid_page(client):
    response = client.patch(
        app.url_for("PasswordReset.update", token="bogus"),
        body={"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
    )

    assert response.status == 200
    assert Session.select().count() == 0
