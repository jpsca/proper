from proper import Concern


class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        headers = self.response.headers

        # Only pages of this site can show this one in a <frame> or <iframe>.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
        headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # The browser uses the `Content-Type` of the response, and doesn't
        # guess another one from the content: an uploaded text file can't
        # run as a script.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Content-Type-Options
        headers.setdefault("X-Content-Type-Options", "nosniff")

        # Turns off the XSS filter of old browsers (current ones don't have
        # it): the filter could be used to leak data from a page. A
        # `Content-Security-Policy` is what protects against XSS now.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
        headers.setdefault("X-XSS-Protection", "0")

        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # For the duration of the max-age (seconds), the browser uses HTTPS for this host, even when
        # given an `http://` link. Browsers ignore it in an HTTP response,
        # so it's only sent over HTTPS.
        # https://developer.mozilla.org/Web/HTTP/Headers/Strict-Transport-Security
        # if self.request.is_secure:
        #     headers.setdefault("Strict-Transport-Security", f"max-age={1 * YEAR}")
