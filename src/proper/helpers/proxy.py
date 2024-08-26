from contextvars import ContextVar


class Current:
    def __init__(self) -> None:
        self._current_app = ContextVar("_current_app", default=None)
        self._current_request = ContextVar("_current_request", default=None)
        self._current_response = ContextVar("_current_response", default=None)

    @property
    def app(self):
        return self._current_app.get()
    @app.setter
    def app(self, value):
        self._current_app.set(value)

    @property
    def request(self):
        return self._current_request.get()

    @request.setter
    def request(self, value):
        self._current_request.set(value)

    @property
    def response(self):
        return self._current_response.get()

    @response.setter
    def response(self, value):
        self._current_response.set(value)


current = Current()
