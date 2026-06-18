from proper.units import HOUR, MINUTES

from [[app_name]].forms.sign_up import SignUpForm
from [[app_name]].main import config
from [[app_name]].models import User
from [[app_name]].router import router
from .app_controller import AppController


@router.resource("sign-up", pk=None)
class SignUpController(AppController):
    skip_authentication = True

    before = [
        {"do": "redirect_if_authenticated"},
        {"do": "set_form"},
        {"do": "validate_form", "only": ["create"]},
    ]
    rate_limit = [
        {"to": 10, "within": 15 * MINUTES, "only": "create"},
        {"to": 30, "within": 1 * HOUR, "only": "create"},
    ]

    def new(self):
        pass

    def create(self):
        data = self.form.save()
        user = User.create(
            login=data["login"],
            password=data["password1"],
        )
        self.new_session_for(user)
        self.redirect_after_authentication(flash="Welcome!")

    # Private

    def set_form(self):
        self.password_minlen = config.AUTH_PASSWORD_MINLEN
        self.form = SignUpForm(self.params)

