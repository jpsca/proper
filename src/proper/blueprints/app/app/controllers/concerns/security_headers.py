from proper import Controller


class SetSecurityHeaders:
    def __call__(self, co: Controller):
        # It determines if a web page can or cannot be included via <frame>
        # and <iframe> topics by untrusted domains.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
        co.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # Determine the behavior of the browser in case an XSS attack is
        # detected. Use Content-Security-Policy without allowing unsafe-inline
        # scripts instead.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
        co.response.headers.setdefault("X-XSS-Protection", "1", mode="block")

        # Download files or try to open them in the browser?
        co.response.headers.setdefault("X-Download-Options", "noopen")

        # Set to none to restrict Adobe Flash Player’s access to the web page data.
        co.response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        co.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
