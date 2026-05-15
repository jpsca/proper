from proper.units import HOUR, MINUTES

from [[app_name]].forms.session import SignInForm
from [[app_name]].models import User
from [[app_name]].router import router
from .app_controller import AppController


@router.resource("sign-in", pk=None)
class SessionController(AppController):
    skip_authentication = True

    before = {"do": "redirect_if_authenticated", "exclude": ["delete"]}
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

    def new(self):
        pass

    def create(self):
        self.reset_rate_limit(self.login_param)
        data = self.form.save()
        user = User.get_by_login(data["login"])
        self.new_session_for(user)
        self.redirect_after_authentication(flash="Welcome back!")

    def delete(self):
        self.terminate_session()
        self.response.redirect_to("/")

    # Private

    def set_form(self):
        self.form = SignInForm(self.params)

    def too_many_retries(self):
        self.response.redirect_to(
            "Session.new",
            flash="Try again in a few minutes or reset your password.",
            flash_type="error",
        )
