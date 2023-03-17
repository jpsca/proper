from proper import Controller, response


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    def __before__(self):
        pass

    def __after__(self):
        self._put_security_headers()

    # Private

    def _put_security_headers(self):
        # It determines if a web page can or cannot be included via <frame>
        # and <iframe> topics by untrusted domains.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
        response.set("X-Frame-Options", "SAMEORIGIN")

        # Determine the behavior of the browser in case an XSS attack is
        # detected. Use Content-Security-Policy without allowing unsafe-inline
        # scripts instead.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
        response.set("X-XSS-Protection", "1", mode="block")

        # Download files or try to open them in the browser?
        response.set("X-Download-Options", "noopen")

        # Set to none to restrict Adobe Flash Player’s access to the web page data.
        response.set("X-Permitted-Cross-Domain-Policies", "none")

        response.set("Referrer-Policy", "strict-origin-when-cross-origin")
