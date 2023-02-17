from proper.router import *  # noqa

from .app import app


app.routes += [
    # Static files that are expected at the root
    get("favicon.ico", redirect="/static/favicon.ico"),
    get("robots.txt", redirect="/static/robots.txt"),
    get("humans.txt", redirect="/static/humans.txt"),
]
