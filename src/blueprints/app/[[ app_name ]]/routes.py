from proper.router import *  # noqa

from .app import app


app.routes += [
    # Static files
    static(
        "static/:file<path>",
        root=app.static_folder,
        name="static",
    ),
    static(
        f"{app.config.COMPONENTS_URL_ROOT}/:file<path>",
        root=app.components_folder,
        allowed_ext=(".css", ".js"),
    ),
    # Static files that are expected at the root
    get("favicon.ico", redirect="/static/favicon.ico"),
    get("robots.txt", redirect="/static/robots.txt"),
    get("humans.txt", redirect="/static/humans.txt"),

]
