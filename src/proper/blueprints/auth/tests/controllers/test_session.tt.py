from [[app_name]].main import app
from [[app_name]].models import Session, User


def test_new_renders_sign_in_page(client):
    response = client.get(app.url_for("Session.new"))
    assert response.status == 200


def test_new_redirects_when_already_authenticated(signed_client):
    response = signed_client.get(app.url_for("Session.new"))
    assert response.status == 303


def test_create_signs_in_with_valid_credentials(client):
    user = User.create(login="bob", password="password123")

    response = client.post(
        app.url_for("Session.create"),
        body={"login": "bob", "password": "password123"},
    )

    assert response.status == 303
    assert response.headers["location"] == "/"
    assert Session.select().where(Session.user == user).count() == 1


def test_create_normalizes_the_login(client):
    user = User.create(login="carol", password="password123")

    # Uppercase and surrounding whitespace must resolve to the same user.
    response = client.post(
        app.url_for("Session.create"),
        body={"login": "  CAROL  ", "password": "password123"},
    )

    assert response.status == 303
    assert Session.select().where(Session.user == user).count() == 1


def test_create_with_wrong_password_does_not_sign_in(client):
    User.create(login="dave", password="password123")

    response = client.post(
        app.url_for("Session.create"),
        body={"login": "dave", "password": "wrong-password"},
    )

    assert response.status == 422
    assert Session.select().count() == 0


def test_create_with_unknown_login_does_not_sign_in(client):
    response = client.post(
        app.url_for("Session.create"),
        body={"login": "nobody", "password": "password123"},
    )

    assert response.status == 422
    assert Session.select().count() == 0


def test_create_with_blank_fields_does_not_sign_in(client):
    response = client.post(
        app.url_for("Session.create"),
        body={"login": "", "password": ""},
    )

    assert response.status == 422
    assert Session.select().count() == 0


def test_delete_redirects(signed_client):
    response = signed_client.delete(app.url_for("Session.delete"))
    assert response.status == 303
