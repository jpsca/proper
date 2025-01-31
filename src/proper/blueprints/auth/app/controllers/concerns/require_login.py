from proper import Controller

from app.main import app


REDIRECT_AFTER_LOGIN_KEY = "_redirect"


class RequireLogin:
    def before(self, co: Controller):
        if co.request.user:
            return

        if REDIRECT_AFTER_LOGIN_KEY not in co.response.session:
            co.response.session[REDIRECT_AFTER_LOGIN_KEY] = co.request.path

        co.response.redirect_to(app.url_for("Sessions.new"))
        return co.response
