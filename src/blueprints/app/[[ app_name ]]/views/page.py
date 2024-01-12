from proper.current import request, response  # noqa

from .app import AppView


class Page(AppView):
    def not_found(self):
        pass

    def error(self):
        pass
