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


def test_no_content_security_policy_by_default(app, SecurityHeaders):
    assert "Content-Security-Policy" not in run(app, SecurityHeaders)


@pytest.fixture()
def WithPolicy(tmp_path):
    """The concern with its commented `Content-Security-Policy` turned on."""
    lines = PATH.read_text().splitlines()
    start = next(
        i for i, line in enumerate(lines) if '# if "Content-Security-Policy" not in headers:' in line
    )
    end = next(i for i, line in enumerate(lines) if i > start and line.split() == ["#", "])"])
    for i in range(start, end + 1):
        lines[i] = lines[i].replace("# ", "", 1)
    path = tmp_path / "security_headers_with_policy.py"
    path.write_text("\n".join(lines) + "\n")
    spec = importlib.util.spec_from_file_location("security_headers_with_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SecurityHeaders


def test_the_commented_content_security_policy_works(app, WithPolicy):
    app.router.static("/assets", root="/tmp/assets", name="assets")

    class _TestController(WithPolicy, Controller):
        def action(self):
            return "OK"

    request = make_test_request("/", app=app)
    request.matched_action = "action"
    response = Response(app)
    _TestController(request, response)._dispatch("action")

    policy = response.headers["Content-Security-Policy"].value
    nonce = response.csp_nonce
    assert f"script-src 'self' {app.importmap_csp_hash} 'nonce-{nonce}'" in policy
    assert f"style-src 'self' 'nonce-{nonce}'" in policy
    assert "'unsafe-inline'" not in policy
    assert policy.startswith("default-src 'self'; ")


def test_a_response_with_its_own_policy_keeps_it_and_gets_no_nonce(app, WithPolicy):
    class _TestController(WithPolicy, Controller):
        def action(self):
            self.response.headers["Content-Security-Policy"] = "default-src 'none'"
            return "OK"

    request = make_test_request("/", app=app)
    request.matched_action = "action"
    response = Response(app)
    _TestController(request, response)._dispatch("action")

    assert response.headers["Content-Security-Policy"].value == "default-src 'none'"
    assert response.session == {}
