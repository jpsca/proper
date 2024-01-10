from proper import Controller

from [[ app_name ]].app import app


REDIRECT_AFTER_LOGIN_KEY = "_redirect"


class RequireLogin:
    def before(self, controller: Controller):
        if self.request.user:
            return
        if REDIRECT_AFTER_LOGIN_KEY not in self.response.session:
            self.response.session[REDIRECT_AFTER_LOGIN_KEY] = self.request.path
        self.response.redirect_to(app.url_for("Auth.sign_in"))
        return self.response
