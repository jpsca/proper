"""
Routes without a controller.
Other routes are defined as decorators and mounted when
the controllers are imported.
"""
from .main import app


router = app.router

# Assets
router.static(app.config.ASSETS_URL, root=app.assets_path, name="assets")

# Root-level assets
router.get("robots.txt", redirect="/assets/robots.txt")
router.get("humans.txt", redirect="/assets/humans.txt")
