from proper import errors

from ..router import router
from .app_controller import AppController


class PublicController(AppController):
    skip_authentication = True

    # --- Uncomment to have an index page ---
    # @router.get("")
    def index(self):
        pass

    @router.error(errors.NotFound)
    @router.get("_not_found")
    def not_found(self):
        pass

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        pass

    @router.get("up")
    def health(self):
        # This page loads nothing, and has no content of anyone: its own
        # policy allows the style of its <body>, whatever the policy of
        # the app says.
        self.response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'"
        )
        return (
            "<!doctype html>\n<html>\n<head><title>Up</title></head>"
            '<body style="background:green"></body>\n</html>'
        )
