from .main import app


router = app.router

# Routes without a controller.
# Other routes are defined as decorators and mounted when
# the controllers are imported
router.static(app.config.STATIC_URL, root=app.static_path, name="static")
router.static(
    app.config.VIEWS_ASSETS_URL,
    root=app.views_path,
    allowed_ext=(".css", ".js", ".png", ".jpg"),
)
router.get("favicon.ico", redirect="/static/favicon.ico"),
router.get("robots.txt", redirect="/static/robots.txt"),
router.get("humans.txt", redirect="/static/humans.txt"),
