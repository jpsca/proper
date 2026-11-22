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

        # Where the scripts, styles and other resources of a page can come
        # from: if someone gets their HTML into a page, the browser refuses
        # to load what this policy doesn't allow. Adjust it to what your app
        # loads before turning it on, and add `{{ csp_meta_tag() }}` to the
        # <head> of your layout, so Turbo can show its progress bar.
        # https://properproject.org/docs/security#content-security-policy
        # if "Content-Security-Policy" not in headers:
        #     nonce = self.response.csp_nonce
        #     headers["Content-Security-Policy"] = "; ".join([
        #         "default-src 'self'",
        #         f"script-src 'self' {self.app.importmap_csp_hash} 'nonce-{nonce}'",
        #         f"style-src 'self' 'nonce-{nonce}'",
        #         "img-src 'self' data:",
        #         "object-src 'none'",
        #         "base-uri 'self'",
        #         "form-action 'self'",
        #         "frame-ancestors 'self'",
        #     ])

        # For the duration of the max-age (seconds), the browser uses HTTPS for this host, even when
        # given an `http://` link. Browsers ignore it in an HTTP response,
        # so it's only sent over HTTPS.
        # https://developer.mozilla.org/Web/HTTP/Headers/Strict-Transport-Security
        # if self.request.is_secure:
        #     headers.setdefault("Strict-Transport-Security", f"max-age={1 * YEAR}")
