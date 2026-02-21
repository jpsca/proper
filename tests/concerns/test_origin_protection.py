import pytest

from proper import Request, Response
from proper.concerns import OriginProtection
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY
from proper.controller import Controller
from proper.errors import InvalidOrigin


class _TestController(Controller, OriginProtection):
    def action(self):
        return "OK"


@pytest.fixture
def co(app):
    request = Request()
    response = Response()
    return _TestController(app, request, response)


# Allow all safe methods (GET, HEAD, OPTIONS, QUERY)
@pytest.mark.parametrize("method", [GET, HEAD, OPTIONS, QUERY])
def test_safe_methods_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    # No origin or sec-fetch-site headers set

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when neither Origin nor Sec-Fetch-Site headers are present
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_no_headers_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    # No headers set

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when Origin is in TRUSTED_ORIGINS
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_trusted_origin_allowed(co, method):
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com", "https://another-trusted.com:8080"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["origin"] = "https://trusted.com"

    # Should not raise InvalidOrigin
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_trusted_origin_with_port_allowed(co, method):
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com:8080"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["origin"] = "https://trusted.com:8080"

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when Sec-Fetch-Site is "same-origin" or "none"
@pytest.mark.parametrize("value", ["same-origin", "none"])
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_sec_fetch_site_same_origin_allowed(co, value, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["sec_fetch_site"] = value

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when Origin matches host_with_port
# Note: The origin needs to match host_with_port exactly (without protocol)
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_matching_origin_and_host_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.env["origin"] = "example.com:8080"

    # Should not raise InvalidOrigin
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_matching_origin_and_host_default_port_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 80
    co.request.env["origin"] = "example.com"

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Reject when none of the conditions are met
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_origin_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.env["origin"] = "https://evil.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_cross_site_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["sec_fetch_site"] = "cross-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_same_site_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["sec_fetch_site"] = "same-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_untrusted_origin_rejected(co, method):
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["origin"] = "https://untrusted.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


# Edge cases
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_mismatched_port_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.env["origin"] = "https://example.com:9090"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_origin_without_port_vs_host_with_port_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.env["origin"] = "https://example.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_standard_http_origin_with_protocol_rejected(co, method):
    # Standard HTTP Origin headers include protocol and won't match host_with_port
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.env["origin"] = "https://example.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_empty_origin_and_sec_fetch_site_present_rejected(co, method):
    # If sec_fetch_site is present but not an allowed value, should reject
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["origin"] = ""
    co.request.env["sec_fetch_site"] = "cross-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_origin_subdomain_mismatch_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.env["origin"] = "https://subdomain.example.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


# Combination tests
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_trusted_origin_with_invalid_sec_fetch_site_allowed(co, method):
    # Trusted origin should be allowed even with cross-site sec_fetch_site
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.env["origin"] = "https://trusted.com"
    co.request.env["sec_fetch_site"] = "cross-site"

    # Should not raise InvalidOrigin because origin is trusted
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_same_origin_sec_fetch_site_with_invalid_origin_allowed(co, method):
    # Valid sec_fetch_site should allow even with mismatched origin
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.env["origin"] = "https://evil.com"
    co.request.env["sec_fetch_site"] = "same-origin"

    # Should not raise InvalidOrigin because sec_fetch_site is same-origin
    co._dispatch("action")
