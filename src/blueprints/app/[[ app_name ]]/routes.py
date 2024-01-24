from proper.router import *  # noqa

from .app import app


app.routes += [
    # Static files
    static(
        app.config.STATIC_URL,
        root=app.static_path,
        name="static",
    ),
    static(
        app.config.COMPONENTS_URL,
        root=app.components_path,
        allowed_ext=(".css", ".js", ".png", ".jpg"),
    ),
    # Static files that are expected at the root
    get("favicon.ico", redirect="/static/favicon.ico"),
    get("robots.txt", redirect="/static/robots.txt"),
    get("humans.txt", redirect="/static/humans.txt"),

]
