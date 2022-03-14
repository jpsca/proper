from proper.router import *  # noqa

from .app import app
from .controllers import *  # noqa


app.routes = [
    # Static files that are expected at the root
    get("favicon.ico", redirect="/static/favicon.ico"),
    get("robots.txt", redirect="/static/robots.txt"),
    get("humans.txt", redirect="/static/humans.txt"),

    # Auth
    get("sign-in", to=Auth.sign_in),
    post("sign-in", to=Auth.sign_in),
    post("sign-out", to=Auth.sign_out),
    scope("password")(
        get("reset", to=Auth.reset),
        post("reset", to=Auth.reset),
        get("reset/:token", to=Auth.reset_validate),
        get("change", to=Auth.password_change),
        post("change", to=Auth.password_change),
    ),
]
