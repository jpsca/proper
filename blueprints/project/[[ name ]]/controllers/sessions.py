from ..forms.session import SignInForm, PasswordResetForm, PasswordChangeForm
from ..app import app
from ..models.user import User

from .application import PublicController
from .concerns.emails.password_reset import send_password_reset_email


class Sessions(PublicController):

    def login(self, req, resp):
        if req.current_user:
            return go_forward(resp)

        self.form = form = SignInForm(req.form)
        if not req.is_post:
            return

        if not form.validate():
            form.error = "Wrong user and/or password"
            return

        # First, we check if there is a user with this credentials
        credentials = form.save()
        user = User.authenticate(**credentials)
        if not user:
            form.error = "Wrong user and/or password"
            return

        # If there is one, THEN we store its token in the session.
        user.auth.login(req)
        return go_forward(resp)

    def logout(self, req, resp):
        if req.current_user:
            req.current_user.auth.logout(req)
        return resp.redirect_to("/")

    def reset(self, req, resp):
        self.form = form = PasswordResetForm(req.form)
        if not req.is_post:
            return

        if not form.validate():
            return

        login = form.save()["login"]
        user = User.get(login=login)
        if not user:
            form.error = "Can't find that email, sorry."
            return

        send_password_reset_email(user)
        self.email = user.login
        resp.template = "sessions/reset_sent"

    def reset_validate(self, req, resp, token):
        user = User.authenticate_token(token)
        if not user:
            resp.template = "sessions/reset_invalid"
            return
        user.auth.login(req)
        resp.redirect_to(app.url_for("Sessions.password_change"))

    def password_change(self, req, resp):
        if not req.current_user:
            return resp.redirect_to(app.url_for("Sessions.login"))

        self.form = form = PasswordChangeForm(req.form)
        if not req.is_post:
            return

        if not form.validate():
            return

        new_password = form.save()["password"][0]
        req.current_user.set_password(new_password)
        # Password has change, so we need to change the user token in the
        # session as well
        req.current_user.auth.login(req)

        go_forward(resp)


def go_forward(resp):
    next_url = resp.session.pop("_redirect", None) or app.url_for("Users.profile")
    resp.redirect_to(next_url)
