import logging
import typing as t
from pathlib import Path

from . import formatters, jsonplus
from .asgi import copy_file
from .dicts import CIMultiDict, DotDict, MultiDict
from .html import dom_id, render_importmap
from .html2text import html2text
from .imports import (
    ImportStringError,
    get_class,
    get_instance,
    import_string,
)
from .render import (
    add_dependencies,
    add_to_concerns,
    call,
    printf,
    render_blueprint,
    sort_imports,
    sort_imports_in,
)
from .server import show_banner, show_welcome


__all__ = (
    "formatters",
    "jsonplus",
    #
    "copy_file",
    #
    "DotDict",
    "CIMultiDict",
    "MultiDict",
    #
    "dom_id",
    "render_importmap",
    #
    "html2text",
    #
    "ImportStringError",
    "get_class",
    "get_instance",
    "import_string",
    #
    "add_dependencies",
    "add_to_concerns",
    "call",
    "printf",
    "render_blueprint",
    "sort_imports",
    "sort_imports_in",
    #
    "show_banner",
    "show_welcome",
    #
    "logger",
    "BLUEPRINTS",
    "make_list",
)


logger = logging.getLogger("proper")
logger.setLevel("DEBUG")
BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()


def make_list(value: t.Any) -> list[t.Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
