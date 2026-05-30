from proper.units import MINUTES

from [[app_name]].emails.password_reset_email import PasswordResetEmail
from [[app_name]].forms.password_reset import PasswordChangeForm, PasswordResetForm
from [[app_name]].main import config
from [[app_name]].models import User
from [[app_name]].router import router
from .app_controller import AppController


@router.resource("password-reset", pk="token")
class PasswordResetController(AppController):
    skip_authentication = True

    before = [
        {"do": "redirect_if_authenticated"},
        {"do": "validate_token", "only": ["edit", "update"]},
    ]
    rate_limit = {
        "to": 10,
        "within": 15 * MINUTES,
        "only": "create",
        "react_with": "too_many_requests",
    }

    def new(self):
        self.form = PasswordResetForm()

    def create(self):
        self.form = PasswordResetForm(self.params)
        if self.form.is_invalid:
            return self.redo()

        login = self.form.save()["login"]
        user = User.get_by_login(login)
        PasswordResetEmail(user).send_later(to=user.email)
        self.response.session["email"] = user.email
        self.response.redirect_to("PasswordReset.show", token="sent")

    def show(self):
        self.email = self.response.session.get("email", "")

    def edit(self):
        self.form = PasswordChangeForm()
        self.login = self.user.login
        self.password_minlen = config.AUTH_PASSWORD_MINLEN

    def update(self):
        self.form = PasswordChangeForm(self.params)
        if self.form.is_invalid:
            self.login = self.user.login
            return self.redo()

        new_password = self.form.save()["password1"]
        self.user.set_password(new_password)
        self.user.save()
        self.new_session_for(self.user)
        self.redirect_after_authentication(flash="Password updated")

    # Private

    def validate_token(self):
        user = User.resolve_token_for(
            "password_reset",
            self.params.get("token"),
            max_age=config.AUTH_TOKEN_LIFE,
        )
        if not user:
            return self.render("password_reset/invalid.jx")
        self.user = user

    def too_many_requests(self):
        self.response.redirect_to(
            "PasswordReset.new",
            flash="Too many requests. Try again in a few minutes.",
            flash_cat="negative",
        )
