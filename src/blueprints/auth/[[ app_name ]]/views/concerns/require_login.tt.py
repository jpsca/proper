from proper import View

from [[ app_name ]].app import app


REDIRECT_AFTER_LOGIN_KEY = "_redirect"


class RequireLogin:
    def before(self, view: View):
        if view.request.user:
            return

        if REDIRECT_AFTER_LOGIN_KEY not in view.response.session:
            view.response.session[REDIRECT_AFTER_LOGIN_KEY] = view.request.path
        view.response.redirect_to(app.url_for("Auth.sign_in"))
        return view.response

    def after(self, view: View):
        pass
