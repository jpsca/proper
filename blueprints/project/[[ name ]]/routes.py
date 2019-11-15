"""These routes are connected to the application in the `main.py` file.
"""
from proper import plugs, scope, get, post

from .auth import auth
from .models.user import User


pipeline_public = [
    plugs.session,
    plugs.protect_from_forgery,
    auth.load(User, session_key="_user_token"),
    plugs.put_secure_headers,
]

pipeline_protected = pipeline_public + [
    auth.login_required(sign_in_url="/sign-in"),
]

routes = [
    scope("/", pipeline_public)(
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
        )
    ),

    scope("/user", pipeline_protected)(
        get("", to="Users.profile"),
    )
]
