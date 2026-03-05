from ..constants import GET, HEAD, OPTIONS, QUERY
from ..errors import InvalidOrigin
from .concern import Concern


__all__ = (
    "OriginProtection",
)
SKIP_FOR_METHODS = (HEAD, GET, OPTIONS, QUERY)


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

    6. Otherwise, reject the request raising an `InvalidOrigin` error.

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
            or (origin and origin == self.request.host_with_port)  # 5
        ):
            return

        # 6
        raise InvalidOrigin()
