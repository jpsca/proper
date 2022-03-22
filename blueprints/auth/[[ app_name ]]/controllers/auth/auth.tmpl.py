from proper import request, response

from [[ app_name ]].app import app, config
from [[ app_name ]].mailers import send_password_reset_email
from [[ app_name ]].models import User
from ..application import AppController
from ..concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from . import forms
from .validators import ERROR_CREDENTIALS


# ERROR_PASSWORD = "We didn't recognize that password"
ERROR_PASSWORD = ERROR_CREDENTIALS


class Auth(AppController):

    def sign_in(self):
        if request.user:
            return self._go_forward()

        self.form = form = forms.SignInForm(self.params)
        if not request.is_post or not form.validate():
            return

        credentials = form.save()
        user = User.authenticate(**credentials)
        if not user:
            form.password.error = ERROR_PASSWORD
            return

        user.sign_in()
        return self._go_forward(flash="Welcome back!")

    def sign_out(self):
        if request.user:
            request.user.sign_out()
        return response.redirect_to("/")

    def reset(self):
        self.form = form = forms.PasswordResetForm(self.params)
        if not request.is_post:
            return

        if not form.validate():
            return

        login = form.save()["login"]
        user = User.by_login(login)
        send_password_reset_email(user)
        self.email = user.email
        return self.render("auth/reset_sent")

    def reset_validate(self, token):
        user = User.authenticate_timestamped_token(token)
        if not user:
            return self.render("auth/reset_invalid")

        user.sign_in(request, response)
        response.redirect_to(app.url_for("Auth.password_change"))

    def password_change(self):
        if not request.user:
            return response.redirect_to(app.url_for("Auth.sign_in"))

        self.form = form = forms.PasswordChangeForm(self.params)
        self.password_minlen = config.auth.password_minlen

        if not request.is_post:
            return

        if not form.validate():
            return

        new_password = form.save()["password"][0]
        request.user.set_new_password(new_password)
        self._go_forward(flash="Password updated")

    # Private

    def _go_forward(self, flash=None):
        next_url = response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        response.redirect_to(next_url, flash=flash)
