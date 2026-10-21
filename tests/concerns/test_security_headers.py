import importlib.util
from pathlib import Path

import pytest

from proper import Response
from proper.controller import Controller
from proper.test_client import make_test_request


# The concern is not part of Proper: it is copied into every new app
PATH = (
    Path(__file__).parents[2]
    / "blueprint" / "[[app_name]]" / "controllers" / "concerns" / "security_headers.py"
)


@pytest.fixture(scope="module")
def SecurityHeaders():
    spec = importlib.util.spec_from_file_location("security_headers", PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SecurityHeaders


def run(app, SecurityHeaders, url="http://example.com/", headers=None):
    class _TestController(SecurityHeaders, Controller):
        def action(self):
            return "OK"

    request = make_test_request(url, app=app)
    request.matched_action = "action"
    response = Response(app)
    if headers:
        response.headers.update(headers)
    _TestController(request, response)._dispatch("action")
    return response.headers


def test_the_headers(app, SecurityHeaders):
    headers = run(app, SecurityHeaders)
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-XSS-Protection") == "0"
    assert headers.get("X-Permitted-Cross-Domain-Policies") == "none"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Download-Options" not in headers


def test_a_header_already_set_is_kept(app, SecurityHeaders):
    headers = run(app, SecurityHeaders, headers={"X-Frame-Options": "DENY"})
    assert headers.get("X-Frame-Options") == "DENY"
