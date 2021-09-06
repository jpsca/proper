from ..app import app
from ..mailers import send_password_reset_email
from ..models import User
from ..services import auth_services

from .application import ApplicationController, REDIRECT_AFTER_LOGIN_KEY
from .forms.auth import PasswordChangeForm, PasswordResetForm, SignInForm


class Auth(ApplicationController):

    def sign_in(self):
        if self.req.user:
            return go_forward(self.resp)

        self.form = form = SignInForm(self.req.form)
        if not self.req.is_post or not form.validate():
            return

        credentials = form.save()
        user = auth_services.authenticate(User, **credentials)
        if not user:
            # msg = "We didn’t recognize that password."
            msg = "Wrong username and/or password"
            form.password.error = msg
            return

        auth_services.sign_in(user, req=self.req, resp=self.resp)
        self.resp.flash("Welcome back!")
        return go_forward(self.resp)

    def sign_out(self):
        if self.req.user:
            auth_services.sign_out(self.req.user, req=self.req, resp=self.resp)
        return self.resp.redirect_to("/")

    def reset(self):
        self.form = form = PasswordResetForm(self.req.form)
        if not self.req.is_post:
            return

        if not form.validate():
            return

        login = form.save()["login"]
        user = User.by_login(login)
        send_password_reset_email(user)
        self.email = user.email
        self.resp.template = "auth/reset_sent"

    def reset_validate(self, token):
        user = auth_services.authenticate_timestamped_token(User, token)
        if not user:
            self.resp.template = "auth/reset_invalid"
            return

        auth_services.sign_in(user, req=self.req, resp=self.resp)
        self.resp.redirect_to(app.url_for("Auth.password_change"))

    def password_change(self):
        if not self.req.user:
            return self.resp.redirect_to(app.url_for("Auth.sign_in"))

        self.form = form = PasswordChangeForm(self.req.form)
        self.password_minlen = app.config.auth_password_minlen

        if not self.req.is_post:
            return

        if not form.validate():
            return

        new_password = form.save()["password"][0]
        auth_services.set_new_password(
            self.req.user,
            new_password,
            req=self.req,
            resp=self._appresp,
        )
        go_forward(self.resp)


def go_forward(resp):
    next_url = resp.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
    resp.redirect_to(next_url)
