import typing as t
from functools import partial

import minijx

from ..global_context import current
from ..helpers import dom_id, render_importmap
from ..helpers.formatters import truncate
from ..turbo import turbo_frame_tag, turbo_stream
from ..turbo.tags import TAGS as TURBO_TAGS


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
        "turbo_frame_tag": turbo_frame_tag,
        "turbo_stream": turbo_stream,
    }

    # The views are compiled to Python modules in `COMPILED_PATH`, one folder
    # per folder of views (`_compiled/views/...`). With DEBUG, a view that
    # changes is compiled again when rendered.
    app.catalog = minijx.Catalog(
        auto_reload=app.config.DEBUG,
        output=app.root_path.parent / app.config.COMPILED_PATH,
        filters=TEMPLATE_FILTERS,
        tags={**TURBO_TAGS, **(app.config.get("TEMPLATE_TAGS") or {})},
        **TEMPLATE_GLOBALS,
    )
