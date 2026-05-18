import json
import typing as t

import jx
from markupsafe import Markup

from ..cache import FragmentCacheExtension
from ..global_context import current


def setup(app):
    def render_importmap():
        importmap = app.config.get("IMPORT_MAP", {})
        imports = {}
        for key, value in importmap.items():
            if value.startswith(("http", "/")):
                imports[key] = value
            else:
                imports[key] = app.url_for("assets", file=value)

        json_imports = json.dumps({"imports": imports})
        return Markup(
            f'<script type="importmap" data-turbo-track="reload">{json_imports}</script>'
        )

    template_filters: dict[str, t.Any] = {}

    template_globals: dict[str, t.Any] = {
        "current": current,
        "url_for": app.url_for,
        "url_is": app.url_is,
        "url_startswith": app.url_startswith,
        "render_importmap": render_importmap,
    }

    app.catalog = jx.Catalog(
        extensions=[
            FragmentCacheExtension,
            *app.config.get("TEMPLATE_EXTENSIONS", []),
        ],
        auto_reload=app.config.DEBUG,
        filters=template_filters,
        **template_globals,
    )
