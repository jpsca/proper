from proper import View


class SecurityHeaders:
    def before(self, view: View):
        pass

    def after(self, view: View):
        # It determines if a web page can or cannot be included via <frame>
        # and <iframe> topics by untrusted domains.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
        view.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # Determine the behavior of the browser in case an XSS attack is
        # detected. Use Content-Security-Policy without allowing unsafe-inline
        # scripts instead.
        # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
        view.response.headers.setdefault("X-XSS-Protection", "1", mode="block")

        # Download files or try to open them in the browser?
        view.response.headers.setdefault("X-Download-Options", "noopen")

        # Set to none to restrict Adobe Flash Player’s access to the web page data.
        view.response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        view.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
