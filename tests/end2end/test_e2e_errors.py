import pytest

from proper import errors, get, status


def test_fallback_not_found(app, web):
    app.router.routes = []

    resp = web.get("/", expect_errors=True)

    assert resp.status == status.not_found
    assert "<title>Page Not Found</title>" in resp.text


def test_fallback_error(app, web):
    app.router.routes = [
        get("fail/not_acceptable", to="Pages.fail_not_acceptable"),
        get("fail/not_implemented", to="Pages.fail_not_implemented"),
        get("fail/forbidden", to="Pages.fail_forbidden"),
    ]

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert "<title>Error</title>" in resp.text

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert "<title>Error</title>" in resp.text

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert "<title>Access Denied</title>" in resp.text


def test_debug_not_found(app, web):
    app.config["debug"] = True
    app.router.routes = []

    resp = web.get("/", expect_errors=True)

    assert resp.status == status.not_found
    assert "<title>Match Not Found</title>" in resp.text


def test_debug_error(app, web):
    app.config["debug"] = True
    app.router.routes = [
        get("/", to="Pages.index"),
        get("fail/not_acceptable", to="Pages.fail_not_acceptable"),
        get("fail/not_implemented", to="Pages.fail_not_implemented"),
        get("fail/forbidden", to="Pages.fail_forbidden"),
    ]

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert "<title>Not Acceptable</title>" in resp.text

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert "<title>Not Implemented</title>" in resp.text

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert "<title>Forbidden</title>" in resp.text


def test_custom_register_not_an_exception(app, web):
    class NotAnException(object):
        pass

    with pytest.raises(AssertionError):
        app.errorhandler(NotAnException, "Pages.custom_not_found")


def test_custom_register_not_even_a_class(app, web):
    with pytest.raises(AssertionError):
        app.errorhandler(5, "Pages.custom_not_found")


def test_custom_error_handlers(app, web):
    app.router.routes = [
        get("fail/not_acceptable", to="Pages.fail_not_acceptable"),
        get("fail/not_implemented", to="Pages.fail_not_implemented"),
        get("fail/forbidden", to="Pages.fail_forbidden"),
        get("fail/value_error", to="Pages.fail_value_error"),
    ]

    app.errorhandler(errors.NotFound, "Pages.custom_not_found_handler")
    app.errorhandler(errors.NotAcceptable, "Pages.custom_not_acceptable_handler")
    app.errorhandler(errors.HTTPError, "Pages.custom_error_handler")
    app.errorhandler(ValueError, "Pages.custom_value_error_handler")

    resp = web.get("/", expect_errors=True)
    assert resp.status == status.not_found
    assert resp.text == "Custom not found handler"

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert resp.text == "Custom not acceptable handler"

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert resp.text == "Custom error handler"

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert resp.text == "Custom error handler"

    resp = web.get("/fail/value_error", expect_errors=True)
    assert resp.status == status.server_error
    assert resp.text == "Custom value error handler"


def test_fallback_from_custom_error_handlers(app, web):
    app.router.routes = [
        get("fail/value_error", to="Pages.fail_value_error")
    ]

    app.errorhandler(errors.HTTPError, "Pages.custom_error_handler")

    resp = web.get("/fail/value_error", expect_errors=True)
    assert resp.status == status.server_error
    assert "<title>Error</title>" in resp.text


def test_do_not_catch_error(app, web):
    app.setup({"catch_all_errors": False})
    app.router.routes = [
        get("fail/value_error", to="Pages.fail_value_error")
    ]

    with pytest.raises(ValueError):
        web.get("/fail/value_error", expect_errors=True)


def boom(*args, **kwargs):
    raise TypeError


def test_error_when_rendering_the_error_page(app, web):
    from proper import error_handlers

    original_func = error_handlers._render_with_jinja
    error_handlers._render_with_jinja = boom

    app.config["debug"] = True
    app.router.routes = []
    resp = web.get("/", expect_errors=True)

    # The original error code is preserved
    assert resp.status == status.not_found
    assert "<title>Error</title>" in resp.text

    error_handlers._render_with_jinja = original_func
