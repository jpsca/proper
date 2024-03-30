from proper.status import unprocessable

from [[ app_name ]].app import config
from [[ app_name ]].mailers import send_password_reset_email
from [[ app_name ]].models import User

from ..app import AppView
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from .forms import PasswordResetModel, PasswordChangeModel


class PasswordReset(AppView):
    def new(self):
        self.form = PasswordResetModel.as_form()
        return self.render("PasswordReset.New")

    def create(self):
        self.form = PasswordResetModel.as_form(self.params)
        if self.form.is_invalid:
            return self.render("PasswordReset.New", status=unprocessable)

        login = self.form.save()["login"]
        user = User.get_by_login(login)
        send_password_reset_email(user)
        self.email = user.email
        return self.render("PasswordReset.Create")

    def edit(self):
        self.pk = self.params.get("pk")
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("PasswordReset.Invalid", status=unprocessable)

        self.login = user.login
        self.form = PasswordChangeModel.as_form()
        self.password_minlen = config.AUTH_PASSWORD_MINLEN
        return self.render("PasswordReset.Edit")

    def update(self):
        self.pk = self.params.get("pk")
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("PasswordReset.Invalid", status=unprocessable)

        self.form = PasswordChangeModel.as_form(self.params)
        if self.form.is_invalid:
            self.login = user.login
            self.password_minlen = config.AUTH_PASSWORD_MINLEN
            return self.render("PasswordReset.Edit", status=unprocessable)

        new_password = self.form.save()["password1"]
        user.set_password(new_password)
        user.save()
        user.sign_in()
        self._go_forward(flash="Password updated")

    # Private

    def _go_forward(self, flash=None):
        next_url = self.response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        self.response.redirect_to(next_url, flash=flash)
