from proper import request, response

from [[ app_name ]].app import app


REDIRECT_AFTER_LOGIN_KEY = "_redirect"


class RequireLogin:
    def __before__(self):
        self._require_login()

    # Private

    def _require_login(self):
        if request.user:
            return
        if REDIRECT_AFTER_LOGIN_KEY not in response.session:
            response.session[REDIRECT_AFTER_LOGIN_KEY] = request.path
        response.redirect_to(app.url_for("Auth.sign_in"))
