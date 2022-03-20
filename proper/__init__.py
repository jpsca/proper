from .app import App, BadSecretKey, _request_cv, _response_cv  # noqa
from .config import *  # noqa
from .controller import *  # noqa
from .helpers import Dot  # noqa
from .request_wrapper import *  # noqa
from .response_wrapper import *  # noqa
from .router import *  # noqa


def __getattr__(name):
    if name == "request":
        return _request_cv.get()
    elif name == "response":
        return _response_cv.get()
    raise AttributeError
