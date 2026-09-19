"""`app.dumps(..., timed=False)`: deterministic tokens that cannot expire."""
import pytest

from proper import App


KEY_A = "a" * 50
KEY_B = "b" * 50


def make_app(*keys):
    return App(__name__, {"SECRET_KEYS": list(keys)})


def test_untimed_tokens_are_deterministic():
    app = make_app(KEY_A)
    assert app.dumps({"id": 1}, salt="x", timed=False) == app.dumps({"id": 1}, salt="x", timed=False)
    assert app.loads(app.dumps({"id": 1}, salt="x", timed=False), salt="x", timed=False) == {"id": 1}


def test_untimed_tokens_depend_on_value_salt_and_key():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    assert token != app.dumps({"id": 2}, salt="x", timed=False)
    assert token != app.dumps({"id": 1}, salt="y", timed=False)
    assert token != make_app(KEY_B).dumps({"id": 1}, salt="x", timed=False)


def test_untimed_loads_rejects_a_wrong_salt_or_a_tampered_token():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    assert app.loads(token, salt="other", timed=False) is None
    assert app.loads(token[:-2] + "zz", salt="x", timed=False) is None
    assert app.loads("garbage", salt="x", timed=False) is None


def test_untimed_loads_tries_every_secret_key():
    token = make_app(KEY_A).dumps({"id": 1}, salt="x", timed=False)
    assert make_app(KEY_B, KEY_A).loads(token, salt="x", timed=False) == {"id": 1}
    assert make_app(KEY_B).loads(token, salt="x", timed=False) is None


def test_the_two_kinds_of_token_are_not_interchangeable():
    app = make_app(KEY_A)
    timed = app.dumps({"id": 1}, salt="x")
    untimed = app.dumps({"id": 1}, salt="x", timed=False)
    assert timed != untimed
    assert app.loads(untimed, salt="x") is None
    assert app.loads(timed, salt="x", timed=False) is None


def test_timed_is_still_the_default():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x")
    assert app.loads(token, salt="x", max_age=60) == {"id": 1}
    value, timestamp = app.loads(token, salt="x", return_timestamp=True)
    assert value == {"id": 1} and timestamp is not None


@pytest.mark.parametrize("kwargs", [{"max_age": 60}, {"return_timestamp": True}])
def test_untimed_loads_refuses_options_that_need_a_timestamp(kwargs):
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    with pytest.raises(ValueError, match="no timestamp"):
        app.loads(token, salt="x", timed=False, **kwargs)
