from [[ app_name ]].app import app
from [[ app_name ]].mailers import send_password_reset_email
from [[ app_name ]].models import User
from ..application import ApplicationController, REDIRECT_AFTER_LOGIN_KEY
from . import forms


class Auth(ApplicationController):

    def sign_in(self):
        if self.req.user:
            return go_forward(self.resp)

        self.form = form = forms.SignInForm(self.req.form)
        if not self.req.is_post or not form.validate():
            return

        credentials = form.save()
        user = User.authenticate(**credentials)
        if not user:
            # msg = "We didn’t recognize that password."
            msg = "Wrong username and/or password"
            form.password.error = msg
            return

        user.sign_in(self.req, self.resp)
        self.resp.flash("Welcome back!")
        return go_forward(self.resp)

    def sign_out(self):
        if self.req.user:
            self.req.user.sign_out()
        return self.resp.redirect_to("/")

    def reset(self):
        self.form = form = forms.PasswordResetForm(self.req.form)
        if not self.req.is_post:
            return

        if not form.validate():
            return

        login = form.save()["login"]
        user = User.by_login(login)
        send_password_reset_email(user)
        self.email = user.email
        self.resp.component = "AuthResetSent"

    def reset_validate(self, token):
        user = User.authenticate_timestamped_token(token)
        if not user:
            self.resp.component = "AuthResetInvalid"
            return

        user.sign_in(self.req, self.resp)
        self.resp.redirect_to(app.url_for("Auth.password_change"))

    def password_change(self):
        if not self.req.user:
            return self.resp.redirect_to(app.url_for("Auth.sign_in"))

        self.form = form = forms.PasswordChangeForm(self.req.form)
        self.password_minlen = app.config.auth_password_minlen

        if not self.req.is_post:
            return

        if not form.validate():
            return

        new_password = form.save()["password"][0]
        self.req.user.set_new_password(
            new_password,
            req=self.req,
            resp=self._appresp,
        )
        go_forward(self.resp)


def go_forward(resp):
    next_url = resp.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
    resp.redirect_to(next_url)
