from proper.status import unprocessable

from app.controllers.app import AppController
from app.controllers.concerns.require_login import REDIRECT_AFTER_LOGIN_KEY
from app.forms.session import SignInForm
from app.models import User
from app.router import auth_router


class SessionController(AppController):
    @auth_router.get("sign-in")
    def new(self):
        if self.request.user:
            return self._go_forward()
        self.form = SignInForm()
        return self.render("pages/session/new.jinja")

    @auth_router.post("sign-in")
    def create(self):
        self.form = form = SignInForm(self.params)
        if form.is_invalid:
            return self.render("pages/session/new.jinja", status=unprocessable)

        login = form.save()["login"]
        user = User.get_by_login(login)
        user.sign_in()
        return self._go_forward(flash="Welcome back!")

    @auth_router.delete("sign-out")
    def delete(self):
        if self.request.user:
            self.request.user.sign_out()

        self.response.redirect_to("/")

    # Private

    def _go_forward(self, flash=None):
        next_url = self.response.session.pop(REDIRECT_AFTER_LOGIN_KEY, None) or "/"
        self.response.redirect_to(next_url, flash=flash)
