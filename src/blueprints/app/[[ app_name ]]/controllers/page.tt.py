from proper import errors

from .app import AppController
from [[app_name]].router import router


class PagesController(AppController):
    @router.get("")
    def index(self):
        return self.render("Page.Index")

    @router.error(errors.NotFound)
    @router.get("_not_found")
    def not_found(self):
        return self.render("Page.NotFound")

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        return self.render("Page.Error")
