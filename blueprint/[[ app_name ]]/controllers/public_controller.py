from proper import errors

from ..router import router
from .app_controller import AppController


class PublicController(AppController):
    skip_authentication = True

    # Uncomment to have an index page
    # @router.get("")
    # def index(self):
    #     pass

    @router.error(errors.NotFound)
    @router.get("_not_found")
    def not_found(self):
        pass

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        pass
