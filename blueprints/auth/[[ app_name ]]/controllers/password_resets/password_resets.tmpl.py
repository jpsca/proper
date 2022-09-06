from proper import response
from proper.status import unprocessable

from [[ app_name ]].app import config
from [[ app_name ]].mailers import send_password_reset_email
from [[ app_name ]].models import User
from ..app import AppController
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from . import forms


class PasswordResets(AppController):
    def new(self):
        self.form = forms.PasswordResetForm()

    def create(self):
        self.form = forms.PasswordResetForm(self.params)
        if not self.form.validate():
            return self.render("PasswordResets.New", status=unprocessable)

        login = self.form.save()["login"]
        user = User.by_login(login)
        send_password_reset_email(user)
        self.email = user.email

    def edit(self):
        self.pk = self.params["pk"]
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("PasswordResets.Invalid", status=unprocessable)

        self.login = user.login
        self.form = forms.PasswordChangeForm()
        self.password_minlen = config.auth.password_minlen

    def update(self):
        self.pk = self.params["pk"]
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("PasswordResets.Invalid", status=unprocessable)

        self.form = forms.PasswordChangeForm(self.params)
        if not self.form.validate():
            self.login = user.login
            self.password_minlen = config.auth.password_minlen
            return self.render("PasswordResets.Edit", status=unprocessable)

        new_password = self.form.save()["password"][0]
        user.set_new_password(new_password)
        user.sign_in()
        self._go_forward(flash="Password updated")

    # Private

    def _go_forward(self, flash=None):
        next_url = response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        response.redirect_to(next_url, flash=flash)
