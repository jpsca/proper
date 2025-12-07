"""
Routes without a controller.
Other routes are defined as decorators and mounted when
the controllers are imported.
"""
from .main import app


router = app.router

# Static files
router.static(app.config.STATIC_URL, root=app.static_path, name="static")

# Root-level static files
router.get("favicon.ico", redirect="/static/favicon.ico")
router.get("robots.txt", redirect="/static/robots.txt")
router.get("humans.txt", redirect="/static/humans.txt")
