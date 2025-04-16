"""
Routes without a controller.
Other routes are defined as decorators and mounted when
the controllers are imported.
"""
from jinjax.utils import get_url_prefix

from .main import app


router = app.router

# Static files
router.static(app.config.STATIC_URL, root=app.static_path, name="static")

# Static files from views with prefixes
for prefix, loader in app.catalog.prefixes.items():
    if not prefix:
        continue
    url_prefix = get_url_prefix(prefix)
    url = f"{app.config.VIEWS_ASSETS_URL}{url_prefix}"
    for root in loader.searchpath[::-1]:
        router.static(
            url,
            root=root,
            allowed_ext=(".css", ".js", ".png", ".jpg", ".svg", ".woff", ".woff2"),
        )

# Static files from views
router.static(
    url=app.config.VIEWS_ASSETS_URL,
    root=app.views_path,
    allowed_ext=(".css", ".js", ".png", ".jpg", ".svg", ".woff", ".woff2"),
)

# Root-level static files
_ = router.get("favicon.ico", redirect="/static/favicon.ico"),
_ = router.get("robots.txt", redirect="/static/robots.txt"),
_ = router.get("humans.txt", redirect="/static/humans.txt"),

