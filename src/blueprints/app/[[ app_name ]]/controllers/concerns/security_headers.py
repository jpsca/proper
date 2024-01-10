from proper import Controller


class SecurityHeaders:
    def after(self, controller: Controller):
        # It determines if a web page can or cannot be included via <frame>
        # and <iframe> topics by untrusted domains.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
        self.response.headers.set("X-Frame-Options", "SAMEORIGIN")

        # Determine the behavior of the browser in case an XSS attack is
        # detected. Use Content-Security-Policy without allowing unsafe-inline
        # scripts instead.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
        self.response.headers.set("X-XSS-Protection", "1", mode="block")

        # Download files or try to open them in the browser?
        self.response.headers.set("X-Download-Options", "noopen")

        # Set to none to restrict Adobe Flash Player’s access to the web page data.
        self.response.headers.set("X-Permitted-Cross-Domain-Policies", "none")

        self.response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin")
