from proper.status import unprocessable

from .. import tasks
from ..forms.password_reset import PasswordChangeForm, PasswordResetForm
from ..main import app, auth, config
from ..models import User
from ..router import auth_router
from .base import BaseController
from .concerns.require_login import REDIRECT_AFTER_LOGIN_KEY


@auth_router.resource("password-reset")
class PasswordResetController(BaseController):
    def new(self):
        self.form = PasswordResetForm()

    def create(self):
        self.form = PasswordResetForm(self.params)
        if self.form.is_invalid:
            return self.render("pages/password_reset/new.jinja", status=unprocessable)

        login = self.form.save()["login"]
        user = User.get_by_login(login)
        send_password_reset_email(user)
        self.response.session["email"] = user.email
        self.response.redirect_to("PasswordReset.email")

    @auth_router.get("password_reset/email")
    def email(self):
        self.email = self.response.session.get("email", "")
        return self.render("pages/password_reset/create.jinja")

    def edit(self):
        self.pk = self.params.get("pk")
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("pages/password_reset/invalid.jinja", status=unprocessable)

        self.login = user.login
        self.form = PasswordChangeForm()
        self.password_minlen = config.AUTH_PASSWORD_MINLEN

    def update(self):
        self.pk = self.params.get("pk")
        user = User.authenticate_timestamped_token(self.pk)
        if not user:
            return self.render("pages/password_reset/invalid.jinja", status=unprocessable)

        self.form = PasswordChangeForm(self.params)
        if self.form.is_invalid:
            self.login = user.login
            self.password_minlen = config.AUTH_PASSWORD_MINLEN
            return self.render("pages/password_reset/edit.jinja", status=unprocessable)

        new_password = self.form.save()["password1"]
        user.set_password(new_password)
        user.save()
        user.sign_in()
        self._go_forward(flash="Password updated")

    # Private

    def _go_forward(self, flash=None):
        next_url = self.response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        self.response.redirect_to(next_url, flash=flash)


def send_password_reset_email(user):
    token = auth.get_timestamped_token(user)
    validate_url = app.url_for("PasswordReset.edit", pk=token)
    reset_url = app.url_for("PasswordReset.new")
    html = app.catalog.render(
        "emails/password_reset.jinja",
        validate_url=f"{config.PROTOCOL}://{config.HOST}{validate_url}",
        reset_url=f"{config.PROTOCOL}://{config.HOST}{reset_url}",
    )

    tasks.email.send_email(
        to=user.email,
        subject="Reset your password",
        body=html,
        html=True,
    )
