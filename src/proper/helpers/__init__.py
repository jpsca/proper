import logging

from . import jsonplus  # noqa
from .digestor import *  # noqa
from .dotdict import *  # noqa
from .http import *  # noqa
from .mixins import *  # noqa
from .multidict import *  # noqa
from .proxy import *  # noqa
from .render import *  # noqa
from .server import *  # noqa
from .utils import *  # noqa


logger = logging.getLogger("proper")
logger.setLevel("DEBUG")
