import logging
import typing as t
from pathlib import Path

from . import jsonplus  # noqa
from .dotdict import *  # noqa
from .html2text import *  # noqa
from .http import *  # noqa
from .imports import *  # noqa
from .json_field import *  # noqa
from .multidict import *  # noqa
from .render import *  # noqa
from .server import *  # noqa


logger = logging.getLogger("proper")
logger.setLevel("DEBUG")
BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()


def make_list(value: t.Any) -> list[t.Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
