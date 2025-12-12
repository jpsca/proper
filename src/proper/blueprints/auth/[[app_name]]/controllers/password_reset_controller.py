from proper.status import unprocessable
from proper.units import MINUTES

from ..emails.password_reset_email import PasswordResetEmail
from ..forms.password_reset import PasswordChangeForm, PasswordResetForm
from ..main import config
from ..models import User
from ..router import auth_router
from .app_controller import AppController


@auth_router.resource("password-reset")
class PasswordResetController(AppController):
    skip_authentication = True
    rate_limit = {
        "to": 10,
        "within": 15 * MINUTES,
        "only": "create",
        "react_with": "_too_may_requests",
    }

    def new(self):
        self.form = PasswordResetForm()

    def create(self):
        self.form = PasswordResetForm(self.params)
        if self.form.is_invalid:
            return self.render("pages/password_reset/new.jinja", status=unprocessable)

        login = self.form.save()["login"]
        user = User.get_by_login(login)
        PasswordResetEmail(user).send_later(to=user.email)
        self.response.session["email"] = user.email
        self.response.redirect_to("PasswordReset.email")

    @auth_router.get("password_reset/email")
    def email(self):
        self.email = self.response.session.get("email", "")
        return self.render("pages/password_reset/create.jinja")

    def edit(self):
        self.pk = self.params.get("pk")
        user = User.check_token(self.pk)
        if not user:
            return self.render("pages/password_reset/invalid.jinja", status=unprocessable)

        self.login = user.login
        self.form = PasswordChangeForm()
        self.password_minlen = config.AUTH_PASSWORD_MINLEN

    def update(self):
        self.pk = self.params.get("pk")
        user = User.check_token(self.pk)
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
        self.redirect_after_authentication(flash="Password updated")

    def _too_may_requests(self):
        self.response.redirect_to(
            "PasswordReset.new",
            flash="Too many requests. Try again in a few minutes.",
            flash_type="error",
        )
