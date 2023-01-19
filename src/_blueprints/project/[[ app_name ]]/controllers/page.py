from proper import request, response  # noqa

from .app import AppController


class Page(AppController):
    def not_found(self):
        pass

    def error(self):
        pass
