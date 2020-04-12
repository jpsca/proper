__all__ = ("Protect",)


class Protect(object):
    def __init__(self, *tests, sign_in_url="/sign-in", redirect_key="_redirect"):
        self.tests = tests
        self.sign_in_url = sign_in_url
        self.redirect_key = redirect_key

    def __call__(self, req, resp, app):
        if resp.dispatched:
            return

        user = req.current_user
        if not user:
            return self.redirect_away(app, req, resp)

        for test in self.tests:
            test_pass = test(user, req)
            if not test_pass:
                return self.redirect_away(app, req, resp)

    def redirect_away(self, app, req, resp):
        if self.redirect_key not in resp.session:
            resp.session[self.redirect_key] = req.path
        resp.redirect_to(self.sign_in_url)
