import pytest

from proper import View, errors, get, status


class Pages(View):
    def index(self):
        return "Hello World!"

    def fail_not_acceptable(self):
        raise errors.NotAcceptable("Do it again!")

    def fail_not_implemented(self):
        raise errors.NotImplemented("It will be ready when it will be ready")

    def fail_forbidden(self):
        raise errors.Forbidden("Go away!")

    def fail_value_error(self):
        raise ValueError("A non-http exception")

    def custom_not_found_handler(self):
        return "Custom not found handler"

    def custom_not_acceptable_handler(self):
        return "Custom not acceptable handler"

    def custom_error_handler(self):
        return "Custom error handler"

    def custom_value_error_handler(self):
        return "Custom value error handler"


def test_fallback_not_found(app):
    app.router.routes = []

    resp = app.get("/qwertyuiop")

    assert resp.status == status.not_found
    assert "<title>Page Not Found" in resp.body


def test_fallback_error(app):
    app.router.routes = [
        get("fail/not_acceptable", to=Pages.fail_not_acceptable),
        get("fail/not_implemented", to=Pages.fail_not_implemented),
        get("fail/forbidden", to=Pages.fail_forbidden),
    ]

    resp = app.get("/fail/not_acceptable")
    assert resp.status == status.not_acceptable
    assert "<title>Error" in resp.body

    resp = app.get("/fail/not_implemented")
    assert resp.status == status.not_implemented
    assert "<title>Error" in resp.body

    resp = app.get("/fail/forbidden")
    assert resp.status == status.forbidden
    assert "<title>Access Denied" in resp.body


def test_debug_not_found(app):
    app.config["DEBUG"] = True
    app.router.routes = []

    resp = app.get("/qwertyuiop")

    assert resp.status == status.not_found
    assert "<title>Match Not Found" in resp.body


def test_debug_error(app):
    app.config["DEBUG"] = True
    app.router.routes = [
        get("/", to=Pages.index),
        get("fail/not_acceptable", to=Pages.fail_not_acceptable),
        get("fail/not_implemented", to=Pages.fail_not_implemented),
        get("fail/forbidden", to=Pages.fail_forbidden),
    ]

    resp = app.get("/fail/not_acceptable")
    assert resp.status == status.not_acceptable
    assert "<title>Not Acceptable" in resp.body

    resp = app.get("/fail/not_implemented")
    assert resp.status == status.not_implemented
    assert "<title>Not Implemented" in resp.body

    resp = app.get("/fail/forbidden")
    assert resp.status == status.forbidden
    assert "<title>Forbidden" in resp.body


def test_custom_register_not_an_exception(app):
    class NotAnException:
        pass

    with pytest.raises(AssertionError):
        app.error_handler(NotAnException, Pages.custom_not_found_handler)


def test_custom_register_not_even_a_class(app):
    with pytest.raises(AssertionError):
        app.error_handler(5, Pages.custom_not_found_handler)


def test_custom_error_handlers(app):
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

    resp = app.get("/qwertyuiop")
    assert resp.status == status.not_found
    assert resp.body == "Custom not found handler"

    resp = app.get("/fail/not_acceptable")
    assert resp.status == status.not_acceptable
    assert resp.body == "Custom not acceptable handler"

    resp = app.get("/fail/not_implemented")
    assert resp.status == status.not_implemented
    assert resp.body == "Custom error handler"

    resp = app.get("/fail/forbidden")
    assert resp.status == status.forbidden
    assert resp.body == "Custom error handler"

    resp = app.get("/fail/value_error")
    assert resp.status == status.server_error
    assert resp.body == "Custom value error handler"


def test_fallback_from_custom_error_handlers(app):
    app.router.routes = [get("fail/value_error", to=Pages.fail_value_error)]

    app.error_handler(errors.HTTPError, Pages.custom_error_handler)

    resp = app.get("/fail/value_error")
    assert resp.status == status.server_error
    assert "<title>Error" in resp.body


def test_do_not_catch_error(app):
    app.config["CATCH_ALL_ERRORS"] = False
    app.router.routes = [get("fail/value_error", to=Pages.fail_value_error)]

    with pytest.raises(ValueError):
        app.get("/fail/value_error")


def test_error_when_rendering_the_error_page(app):
    from proper.core import error_handlers

    def boom(*args, **kw):
        raise TypeError

    original = error_handlers.jinja_render
    error_handlers.jinja_render = boom

    app.config["DEBUG"] = True
    app.router.routes = []
    resp = app.get("/")

    # The original error code is preserved
    assert resp.status == status.not_found
    assert "<title>Error" in resp.body

    error_handlers.jinja_render = original


def test_register_a_test_error_route_if_in_debug(app):
    app.config["DEBUG"] = True
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error),
    ]
    app.error_handler(ValueError, Pages.custom_value_error_handler)

    last_route = app.router.routes[-1]
    assert last_route.path == "/_value_error"
    assert last_route.to == Pages.custom_value_error_handler


def test_do_not_register_a_test_error_route_if_not_in_debug(app):
    app.config["DEBUG"] = False
    app.router.routes = [
        get("fail/value_error", to=Pages.fail_value_error),
    ]
    app.error_handler(ValueError, Pages.custom_value_error_handler)

    last_route = app.router.routes[-1]
    assert last_route.path != "_value_error"
    assert last_route.to != Pages.custom_value_error_handler
