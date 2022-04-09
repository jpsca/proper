from proper import request, response  # noqa

from .application import AppController


class Page(AppController):
    def not_found(self):
        pass

    def error(self):
        pass
