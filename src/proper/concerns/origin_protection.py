import ipaddress
from urllib.parse import urlparse

from ..constants import GET, HEAD, OPTIONS, QUERY
from ..errors import InvalidOrigin
from .concern import Concern


__all__ = (
    "OriginProtection",
)

SKIP_FOR_METHODS = (HEAD, GET, OPTIONS, QUERY)

LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _is_local_network(hostname: str) -> bool:
    """Return True if the hostname is localhost or a private/link-local IP."""
    if hostname in LOCAL_HOSTNAMES:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP literal (e.g. "mypc.local") - not trusted
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local


class OriginProtection(Concern):
    """Verify that the request comes from the same site or an allowed origin.

    This uses the following algorithm:

    1. Allow all GET, HEAD, OPTIONS, or QUERY requests.
       These are safe methods and are assumed not to change state.

    2. If neither the `Sec-Fetch-Site` nor the `Origin` headers are present, allow the request.
       These requests are not from browsers and can’t be affected by CSRF.

    3. If the `Origin` header matches an allow-list of trusted origins, allow the request.
       The list of trusted origins comes from the `TRUSTED_ORIGINS` config option.
       Trusted origins should include protocol and port (e.g. https://example.com).

    4. If the `Sec-Fetch-Site` header is present and its value is `same-origin` or `none`,
       allow the request; otherwise, reject the request.
       This secures all major up-to-date browsers for sites hosted on trustworthy
       (HTTPS or localhost) origins.

    5. If the `Origin` header’s host (including the port) matches the `Host` header, allow the
       request. This is either a request to an HTTP origin or from an out-of-date browser.

    6. If both the `Origin` and the `Host` are on the local network (private IPs, loopback,
       or link-local addresses), allow the request. This enables development across LAN devices.

    7. Otherwise, reject the request raising an `InvalidOrigin` error.

    """
    before = {"do": "check_request_origin"}

    def check_request_origin(self) -> None:
        if self.request.method in SKIP_FOR_METHODS:  # 1
            return

        origin = self.request.headers.get("origin")
        sec_fetch_site = self.request.headers.get("sec-fetch-site")

        if (
            (origin is None and sec_fetch_site is None)  # 2
            or (origin in self.app.config.get("TRUSTED_ORIGINS", []))  # 3
            or (sec_fetch_site in ("same-origin", "none"))  # 4
            or (origin and urlparse(origin).netloc == self.request.host_with_port)  # 5
        ):
            return

        # 6 - allow local-network to local-network requests
        if origin:
            origin_host = urlparse(origin).hostname or ""
            request_host = self.request.host
            if _is_local_network(origin_host) and _is_local_network(request_host):
                return

        # 7
        raise InvalidOrigin()
