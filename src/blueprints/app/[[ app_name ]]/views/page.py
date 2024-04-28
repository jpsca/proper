from .app import AppView


class Page(AppView):
    def index(self):
        return self.render("Page.Index")

    def not_found(self):
        return self.render("Page.NotFound")

    def error(self):
        return self.render("Page.Error")
