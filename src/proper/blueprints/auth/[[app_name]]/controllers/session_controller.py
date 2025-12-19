from proper.status import unprocessable
from proper.units import HOUR, MINUTES

from ..forms.session import SignInForm
from ..models import User
from ..router import auth_router
from .app_controller import AppController


class SessionController(AppController):
    skip_authentication = True
    rate_limit = [
        {
            "to": 8,
            "within": 15 * MINUTES,
            "only": "create",
            "by": lambda self: self.login_param,
            "react_with": "too_many_retries",
        },
        {"to": 50, "within": 1 * HOUR, "only": "create"},
    ]

    @property
    def login_param(self):
        return User.normalize_login(self.params.get("login") or "")

    @auth_router.get("sign-in")
    def new(self):
        if self.is_authenticated():
            self.redirect_after_authentication(flash="Welcome back!")

        self.form = SignInForm()

    @auth_router.post("sign-in")
    def create(self):
        if self.is_authenticated():
            self.redirect_after_authentication(flash="Welcome back!")
            return

        self.form = form = SignInForm(self.params)
        if form.is_invalid:
            return self.render("pages/session/new.jinja", status=unprocessable)

        self.reset_rate_limit(self.login_param)
        data = form.save()
        user = User.get_by_login(data["login"])
        self.new_session_for(user)
        self.redirect_after_authentication(flash="Welcome back!")

    @auth_router.delete("sign-out")
    def delete(self):
        self.terminate_session()
        self.response.redirect_to("/")

    def too_many_retries(self):
        self.response.redirect_to(
            "Session.new",
            flash="Try again in a few minutes or reset your password.",
            flash_type="error",
        )
