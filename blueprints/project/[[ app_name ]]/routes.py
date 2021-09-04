"""These routes are connected to the application in the `main.py` file.
"""
from proper.router import *  # noqa

from .controllers import *  # noqa


routes = [
    # Static files that are expected at the root
    get("favicon.ico", redirect="/static/favicon.ico"),
    get("robots.txt", redirect="/static/robots.txt"),
    get("humans.txt", redirect="/static/humans.txt"),

    # This routes exist so you can test your error pages
    # but we need to use `app.errorhandler()` (like we do in `app.py`
    # to *actually* use them for handling errors.
    get("_not_found", to=Pages.not_found),
    get("_error", to=Pages.error),

    # Auth
    get("sign-in", to=Auth.sign_in),
    post("sign-in", to=Auth.sign_in),
    post("sign-out", to=Auth.sign_out),
    scope("password")([
        get("reset", to=Auth.reset),
        post("reset", to=Auth.reset),
        get("reset/:token", to=Auth.reset_validate),
        get("change", to=Auth.password_change),
        post("change", to=Auth.password_change),
    ]),

    # Your routes below
    get("", to=Pages.index),
]
