"""The validators of the auth addon's forms, and the normalization of the
logins they check, as `proper install auth` writes them into an app."""
import importlib

import pytest

from .conftest import APP_NAME


@pytest.fixture()
def v(models):
    return importlib.import_module(f"{APP_NAME}.forms.auth.validators")


@pytest.mark.parametrize("login, normalized", [
    ("  Admin@Example.COM ", "admin@example.com"),
    ("Jane Doe", "janedoe"),
    # Full-width letters are the same letters
    ("ｕｓｅｒ@example.com", "user@example.com"),
    # An international domain, in punycode
    ("ana@münchen.de", "ana@xn--mnchen-3ya.de"),
    ("ana@MÜNCHEN.de", "ana@xn--mnchen-3ya.de"),
    ("ana@xn--mnchen-3ya.de", "ana@xn--mnchen-3ya.de"),
    # IDNA 2008, as the registries: not `strasse.de`
    ("ana@straße.de", "ana@xn--strae-oqa.de"),
    # A Cyrillic `а` in the domain is visible in punycode
    ("ana@аpple.com", "ana@xn--pple-43d.com"),
    # The name before the `@` is not changed
    ("josé@example.com", "josé@example.com"),
    # Only the last `@` starts the domain
    ('"a@b"@münchen.de', '"a@b"@xn--mnchen-3ya.de'),
    # Not a valid domain: left as it is
    ("ana@münchen..de", "ana@münchen..de"),
    ("", ""),
])
def test_normalize_login(models, login, normalized):
    assert models.User.normalize_login(login) == normalized


@pytest.mark.parametrize("login", [
    "admin",
    "admin@example.com",
    "jose.perez+news@example.com",
    "ｕｓｅｒ@example.com",
    "ana@münchen.de",
    "ana@аpple.com",
])
def test_an_ascii_login_is_accepted(v, login):
    v.login_is_ascii(login)


@pytest.mark.parametrize("login", [
    # A Cyrillic `а` among Latin letters
    "аdmin",
    "аdmin@example.com",
    # A Latin alpha
    "ɑdmin@example.com",
    "josé@example.com",
    "田中@example.com",
    "ana@münchen..de",
])
def test_a_login_with_other_letters_is_refused(v, login):
    with pytest.raises(ValueError) as exc:
        v.login_is_ascii(login)
    assert exc.value.args[0] == v.ERROR_LOGIN_NOT_ASCII
    assert v.ERROR_LOGIN_NOT_ASCII in v.MESSAGES


def test_the_sign_up_form_refuses_a_login_with_other_letters(models):
    forms = importlib.import_module(f"{APP_NAME}.forms.sign_up")
    form = forms.SignUpForm()
    with pytest.raises(ValueError):
        form.validate_login("аdmin@example.com")
    assert form.validate_login("admin@example.com") == "admin@example.com"


def test_an_international_domain_signs_in_as_it_was_signed_up(models):
    user = models.User.create(login="ana@münchen.de", password="a-long-password")
    assert user.login == "ana@xn--mnchen-3ya.de"
    assert models.User.get_by_login("ANA@münchen.de") == user
    assert models.User.get_by_login("ana@xn--mnchen-3ya.de") == user
