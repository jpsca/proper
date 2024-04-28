from proper.router import (
    delete,  # noqa
    get,  # noqa
    options,  # noqa
    patch,  # noqa
    post,  # noqa
    put,  # noqa
    query,  # noqa
    resource,  # noqa
    restore,  # noqa
    static,  # noqa
)

from .app import app
# from .views.page import Page


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

    # get("", to=Page.index),

]
