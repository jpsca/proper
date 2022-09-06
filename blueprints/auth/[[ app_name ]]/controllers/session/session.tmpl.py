from proper import request, response

from [[ app_name ]].models import User
from ..application import AppController
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from .forms import SignInForm


ERROR_CREDENTIALS = "Wrong username and/or password"


class Session(AppController):
    def new(self):
        if request.user:
            return self._go_forward()
        self.form = SignInForm()

    def create(self):
        user = User.authenticate(
            login=self.params.get("login"),
            password=self.params.get("password"),
        )
        if user:
            user.sign_in()
            return self._go_forward(flash="Welcome back!")

        self.form = SignInForm(self.params)
        self.form.login.error = ERROR_CREDENTIALS
        return self.render("Session.New")

    def delete(self):
        if request.user:
            request.user.sign_out()
        response.redirect_to("/")

    # Private

    def _go_forward(self, flash=None):
        next_url = response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        response.redirect_to(next_url, flash=flash)
