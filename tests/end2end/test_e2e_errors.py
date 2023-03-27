import pytest

from proper import errors, get, status


def test_fallback_not_found(app, web):
    app.router.routes = []

    resp = web.get("/qwertyuiop", expect_errors=True)

    assert resp.status == status.not_found
    assert "<title>Page Not Found" in resp.text


def test_fallback_error(app, Pages, web):
    app.router.routes = [
        get("fail/not_acceptable", to=Pages.fail_not_acceptable),
        get("fail/not_implemented", to=Pages.fail_not_implemented),
        get("fail/forbidden", to=Pages.fail_forbidden),
    ]

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert "<title>Error" in resp.text

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert "<title>Error" in resp.text

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert "<title>Access Denied" in resp.text


def test_debug_not_found(app, web):
    app.config["debug"] = True
    app.router.routes = []

    resp = web.get("/qwertyuiop", expect_errors=True)

    assert resp.status == status.not_found
    assert "<title>Match Not Found" in resp.text


def test_debug_error(app, Pages, web):
    app.config["debug"] = True
    app.router.routes = [
        get("/", to=Pages.index),
        get("fail/not_acceptable", to=Pages.fail_not_acceptable),
        get("fail/not_implemented", to=Pages.fail_not_implemented),
        get("fail/forbidden", to=Pages.fail_forbidden),
    ]

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert "<title>Not Acceptable" in resp.text

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert "<title>Not Implemented" in resp.text

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert "<title>Forbidden" in resp.text


def test_custom_register_not_an_exception(app, Pages):
    class NotAnException:
        pass

    with pytest.raises(AssertionError):
        app.error_handler(NotAnException, Pages.custom_not_found_handler)


def test_custom_register_not_even_a_class(app, Pages):
    with pytest.raises(AssertionError):
        app.error_handler(5, Pages.custom_not_found_handler)


def test_custom_error_handlers(app, Pages, web):
    app.router.routes = [
        get("fail/not_acceptable", to=Pages.fail_not_acceptable),
        get("fail/not_implemented", to=Pages.fail_not_implemented),
        get("fail/forbidden", to=Pages.fail_forbidden),
        get("fail/value_error", to=Pages.fail_value_error),
    ]

    app.error_handler(errors.NotFound, Pages.custom_not_found_handler)
    app.error_handler(errors.NotAcceptable, Pages.custom_not_acceptable_handler)
    app.error_handler(errors.HTTPError, Pages.custom_error_handler)
    app.error_handler(ValueError, Pages.custom_value_error_handler)

    resp = web.get("/qwertyuiop", expect_errors=True)
    assert resp.status == status.not_found
    assert resp.body == b"Custom not found handler"

    resp = web.get("/fail/not_acceptable", expect_errors=True)
    assert resp.status == status.not_acceptable
    assert resp.body == b"Custom not acceptable handler"

    resp = web.get("/fail/not_implemented", expect_errors=True)
    assert resp.status == status.not_implemented
    assert resp.body == b"Custom error handler"

    resp = web.get("/fail/forbidden", expect_errors=True)
    assert resp.status == status.forbidden
    assert resp.body == b"Custom error handler"

    resp = web.get("/fail/value_error", expect_errors=True)
    assert resp.status == status.server_error
    assert resp.body == b"Custom value error handler"


def test_fallback_from_custom_error_handlers(app, Pages, web):
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error)
    ]

    app.error_handler(errors.HTTPError, Pages.custom_error_handler)

    resp = web.get("/fail/value_error", expect_errors=True)
    assert resp.status == status.server_error
    assert "<title>Error" in resp.text


def test_do_not_catch_error(app, Pages, web):
    app.config["catch_all_errors"] = False
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error)
    ]

    with pytest.raises(ValueError):
        web.get("/fail/value_error", expect_errors=True)


def boom(*args, **kw):
    raise TypeError


def test_error_when_rendering_the_error_page(app, web):
    from proper import error_handlers

    original = error_handlers.jinja_render
    error_handlers.jinja_render = boom

    app.config["debug"] = True
    app.router.routes = []
    resp = web.get("/", expect_errors=True)

    # The original error code is preserved
    assert resp.status == status.not_found
    assert "<title>Error" in resp.text

    error_handlers.jinja_render = original


def test_register_a_test_error_route_if_in_debug(app, Pages):
    app.config["debug"] = True
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error),
    ]
    app.error_handler(ValueError, Pages.custom_value_error_handler)

    last_route = app.router.routes[-1]
    assert last_route.path == "/_value_error"
    assert last_route.to == Pages.custom_value_error_handler


def test_do_not_register_a_test_error_route_if_not_in_debug(app, Pages):
    app.config["debug"] = False
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error),
    ]
    app.error_handler(ValueError, Pages.custom_value_error_handler)

    last_route = app.router.routes[-1]
    assert last_route.path != "_value_error"
    assert last_route.to != Pages.custom_value_error_handler
