import pytest

from proper import Request, Response
from proper.concerns import OriginProtection
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY
from proper.controller import Controller
from proper.errors import InvalidOrigin
from proper.request.utils import make_test_scope


class _TestController(Controller, OriginProtection):
    def action(self):
        return "OK"


def _make_co(app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return _TestController(request, response)


@pytest.fixture
def co(app):
    return _make_co(app)


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
    co.request.headers["origin"] = "https://trusted.com"

    # Should not raise InvalidOrigin
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_trusted_origin_with_port_allowed(co, method):
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com:8080"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["origin"] = "https://trusted.com:8080"

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when Sec-Fetch-Site is "same-origin" or "none"
@pytest.mark.parametrize("value", ["same-origin", "none"])
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_sec_fetch_site_same_origin_allowed(co, value, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["sec-fetch-site"] = value

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Allow when Origin's host matches host_with_port
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_matching_origin_and_host_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.headers["origin"] = "https://example.com:8080"

    # Should not raise InvalidOrigin
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_matching_origin_and_host_default_port_allowed(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 80
    co.request.headers["origin"] = "http://example.com"

    # Should not raise InvalidOrigin
    co._dispatch("action")


# Reject when none of the conditions are met
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_origin_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.headers["origin"] = "https://evil.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_cross_site_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["sec-fetch-site"] = "cross-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_same_site_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["sec-fetch-site"] = "same-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_untrusted_origin_rejected(co, method):
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["origin"] = "https://untrusted.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


# Edge cases
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_mismatched_port_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.headers["origin"] = "https://example.com:9090"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_origin_without_port_vs_host_with_port_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 8080
    co.request.headers["origin"] = "https://example.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_standard_https_origin_with_protocol_allowed(co, method):
    # Standard HTTP Origin headers include protocol; netloc should match host_with_port
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.protocol = "https"
    co.request.headers["origin"] = "https://example.com"

    # Should not raise InvalidOrigin
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_empty_origin_and_sec_fetch_site_present_rejected(co, method):
    # If sec-fetch-site is present but not an allowed value, should reject
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["origin"] = ""
    co.request.headers["sec-fetch-site"] = "cross-site"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_origin_subdomain_mismatch_rejected(co, method):
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.headers["origin"] = "https://subdomain.example.com"

    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


# Combination tests
@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_trusted_origin_with_invalid_sec_fetch_site_allowed(co, method):
    # Trusted origin should be allowed even with cross-site sec-fetch-site
    co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com"]
    co.request.method = method
    co.request.matched_action = "action"
    co.request.headers["origin"] = "https://trusted.com"
    co.request.headers["sec-fetch-site"] = "cross-site"

    # Should not raise InvalidOrigin because origin is trusted
    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_same_origin_sec_fetch_site_with_invalid_origin_allowed(co, method):
    # Valid sec-fetch-site should allow even with mismatched origin
    co.request.method = method
    co.request.matched_action = "action"
    co.request.host = "example.com"
    co.request.port = 443
    co.request.headers["origin"] = "https://evil.com"
    co.request.headers["sec-fetch-site"] = "same-origin"

    # Should not raise InvalidOrigin because sec-fetch-site is same-origin
    co._dispatch("action")


# Local-network to local-network requests allowed (step 6)

def _make_local_co(app, origin, host, port=2300):
    co = _make_co(app)
    co.request.method = POST
    co.request.matched_action = "action"
    co.request.host = host
    co.request.port = port
    co.request.headers["origin"] = origin
    return co


@pytest.mark.parametrize("origin,host", [
    ("http://192.168.1.50:2300", "192.168.1.100"),
    ("http://10.0.0.5:2300", "10.0.0.1"),
    ("http://172.16.0.10:2300", "172.16.0.20"),
    ("http://127.0.0.1:2300", "192.168.1.100"),
    ("http://192.168.1.50:2300", "127.0.0.1"),
    ("http://localhost:2300", "192.168.1.100"),
    ("http://192.168.1.50:2300", "localhost"),
    ("http://[::1]:2300", "192.168.1.100"),
    ("http://192.168.1.50:2300", "::1"),
    ("http://localhost:2300", "localhost"),
    ("http://[fe80::1]:2300", "192.168.1.100"),  # link-local IPv6
])
def test_local_network_to_local_network_allowed(app, origin, host):
    co = _make_local_co(app, origin, host)
    co._dispatch("action")


@pytest.mark.parametrize("origin,host", [
    ("https://evil.com", "192.168.1.100"),  # public origin to local host
    ("http://192.168.1.50:2300", "example.com"),  # local origin to public host
    ("https://evil.com", "example.com"),  # both public, mismatched
])
def test_local_network_mixed_rejected(app, origin, host):
    co = _make_local_co(app, origin, host)
    with pytest.raises(InvalidOrigin):
        co._dispatch("action")


def test_non_ip_local_hostname_not_trusted(app):
    """Non-IP hostnames like 'mypc.local' are not trusted as local network."""
    co = _make_local_co(app, "http://mypc.local:2300", "192.168.1.100")
    with pytest.raises(InvalidOrigin):
        co._dispatch("action")
