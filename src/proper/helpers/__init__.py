import logging
import typing as t
from pathlib import Path

from . import formatters, jsonplus  # noqa
from .dotdict import DotDict  # noqa
from .html2text import html2text  # noqa
from .imports import (  # noqa
    ImportStringError,
    get_class,
    get_instance,
    import_string,
)
from .multidict import CIMultiDict, MultiDict  # noqa
from .render import (  # noqa
    add_dependencies,
    add_to_concerns,
    call,
    printf,
    render_blueprint,
    sort_imports,
    sort_imports_in,
)
from .server import show_banner, show_welcome  # noqa
from .streams import copy_file  # noqa


logger = logging.getLogger("proper")
logger.setLevel("DEBUG")
BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()


def make_list(value: t.Any) -> list[t.Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
