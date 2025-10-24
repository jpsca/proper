import logging
from pathlib import Path

from . import jsonplus  # noqa
from .digestor import *  # noqa
from .dotdict import *  # noqa
from .http import *  # noqa
from .json_field import *  # noqa
from .multidict import *  # noqa
from .render import *  # noqa
from .server import *  # noqa
from .utils import *  # noqa


logger = logging.getLogger("proper")
logger.setLevel("DEBUG")
BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()
