from [[ app_name ]].models import User

from ..app import AppView
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from .forms import SignInModel


class Session(AppView):
    def new(self):
        if self.request.user:
            return self._go_forward()
        self.form = SignInModel.as_form()
        return self.render("Session.New")

    def create(self):
        self.form = form = SignInModel.as_form(self.params)
        if form.is_invalid:
            return self.render("Session.New")

        login = form.save()["login"]
        user = User.get_by_login(login)
        user.sign_in()
        return self._go_forward(flash="Welcome back!")

    def delete(self):
        msg = ""
        if self.request.user:
            self.request.user.sign_out()

        self.response.redirect_to("/")

    # Private

    def _go_forward(self, flash=None):
        next_url = self.response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        self.response.redirect_to(next_url, flash=flash)
