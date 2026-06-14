import typing as t
from functools import partial

import jx

from ..cache import FragmentCacheExtension
from ..global_context import current
from ..helpers import dom_id, render_importmap
from ..helpers.formatters import truncate


def setup(app):
    TEMPLATE_FILTERS: dict[str, t.Any] = {
        "truncate": truncate,
    }

    TEMPLATE_GLOBALS: dict[str, t.Any] = {
        "current": current,
        "url_for": app.url_for,
        "url_is": app.url_is,
        "url_startswith": app.url_startswith,
        "render_importmap": partial(render_importmap, app),
        "dom_id": dom_id,
        "truncate": truncate,
    }

    app.catalog = jx.Catalog(
        extensions=[
            FragmentCacheExtension,
            *app.config.get("TEMPLATE_EXTENSIONS", []),
        ],
        auto_reload=app.config.DEBUG,
        filters=TEMPLATE_FILTERS,
        **TEMPLATE_GLOBALS,
    )
