"""These routes are connected to the application in the `main.py` file.
"""
from proper import scope, get, post


routes = [
    scope("/")(
        get("", to="Pages.index"),
        # This routes exist so you can test your error pages
        # but we need to use `app.errorhandler()` (like we do in `app.py`
        # to *actually* use them for handling errors.
        get("_not_found", to="Pages.test_not_found"),
        get("_error", to="Pages.test_error"),
        # A route for building the URLs of static files, even if
        # the application is not going to serve them.
        get("static/:file", to="", name="static", rules={"file": "path"}),
        # Static files that are expected at the root
        get("favicon.ico", redirect="/static/favicon.ico"),
        get("robots.txt", redirect="/static/robots.txt"),
        get("humans.txt", redirect="/static/humans.txt"),
        # Auth
        get("sign-in", to="Sessions.login"),
        post("sign-in", to="Sessions.login"),
        post("sign-out", to="Sessions.logout"),
        scope("/password")(
            get("reset", to="Sessions.reset"),
            post("reset", to="Sessions.reset"),
            get("reset/:token", to="Sessions.reset_validate"),
            get("change", to="Sessions.password_change"),
            post("change", to="Sessions.password_change"),
        ),
    ),
    scope("/user")(get("", to="Users.profile"),),
]
