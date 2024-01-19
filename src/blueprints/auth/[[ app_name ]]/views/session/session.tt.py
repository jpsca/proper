from [[ app_name ]].models import User

from ..app import AppView
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from .forms import SignInForm


ERROR_CREDENTIALS = "Wrong username and/or password"


class Session(AppView):
    def new(self):
        if self.request.user:
            return self._go_forward()
        self.form = SignInForm()
        return self.render("Session.New")

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
        msg = ""
        if self.request.user:
            msg = f"User {self.request.user.username} deleted"
            self.request.user.sign_out()

        self.response.redirect_to("/", flash=msg)

    # Private

    def _go_forward(self, flash=None):
        next_url = self.response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        self.response.redirect_to(next_url, flash=flash)
