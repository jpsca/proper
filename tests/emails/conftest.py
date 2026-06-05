import pytest

from proper.emails.utils import DNS_NAME


@pytest.fixture(autouse=True, scope="session")
def _warm_dns_cache():
    # socket.getfqdn() can take ~5s on machines with slow reverse DNS.
    # Pre-seed the cached FQDN so the mailer never calls it during tests.
    DNS_NAME._fqdn = "localhost"


@pytest.fixture(autouse=True)
def _app_context(app):
    """EmailMessage reads current.app in __init__, so every email test
    needs an active app context."""
    return app
