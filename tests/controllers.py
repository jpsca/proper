"""A mock controller for testing.
"""
from proper import BaseController, errors


class AppController(BaseController):
    def _render(self, req, resp):
        return f"<html>{resp.template} was rendered</html>"


class Pages(AppController):
    def index(self, req, resp, *args):
        resp.body = "Hello World!"
        resp.content_type = "text/plain"
        assert resp.content_type == "text/plain"

    def echo(self, req, resp, *args):
        resp.raw_body = req.stream

    def rendered(self, req, resp, *args):
        pass

    def fail_not_acceptable(self, req, resp):
        raise errors.NotAcceptable("Do it again!")

    def fail_not_implemented(self, req, resp):
        raise errors.NotImplemented("It will be ready when it will be ready")

    def fail_forbidden(self, req, resp):
        raise errors.Forbidden("Go away!")

    def fail_value_error(self, req, resp):
        raise ValueError("A non-http exception")

    def custom_not_found_handler(self, req, resp, app):
        resp.body = "Custom not found handler"

    def custom_not_acceptable_handler(self, req, resp, app):
        resp.body = "Custom not acceptable handler"

    def custom_error_handler(self, req, resp, app):
        resp.body = "Custom error handler"

    def custom_value_error_handler(self, req, resp, app):
        resp.body = "Custom value error handler"

    def append(self, req, resp):
        resp.body = (resp.body or "") + "-index-"

    def set_template(self, req, resp):
        resp.template = "from_controller.jinja"

    def redirect(self, req, resp):
        resp.redirect_to("http://example.com")

    def json(self, req, resp):
        resp.body = {"Hello": "World"}

    def charset(self, req, resp):
        resp.charset = "latin1"
        resp.body = "Hello World!"
