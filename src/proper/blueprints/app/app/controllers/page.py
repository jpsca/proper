from proper import errors

from .app import AppController
from app.router import router


class PageController(AppController):
    # Uncomment to add a home page
    # @router.get("")
    # def index(self):
    #     return self.render("Page.Index")

    @router.error(errors.NotFound)
    @router.get("_not_found")
    def not_found(self):
        return self.render("Page.NotFound")

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        return self.render("Page.Error")
