from pathlib import Path
from datetime import datetime

import jinja2
from proper import BaseController, cached_property, plugs

from ..app import app
from ..auth import auth
from ..models.user import User


class ApplicationController(BaseController):
    """All other controllers must inherit from this class.
    The `_render` method will be called by Proper to render
    your templates.
    """

    def _render(self, req, resp):
        # resp.template doesn't have a extension
        template = resp.template + resp.format
        return render(template, app=app, req=req, **self._as_dict())

    @cached_property
    def now(self):
        return datetime.utcnow()


class PublicController(ApplicationController):

    _plugs = [
        plugs.session,
        plugs.protect_from_forgery,
        auth.load(User, session_key="_user_token"),
        plugs.put_secure_headers,
    ]


class PrivateController(ApplicationController):

    _plugs = [
        plugs.session,
        plugs.protect_from_forgery,
        auth.load(User, session_key="_user_token"),
        auth.login_required(sign_in_url="/sign-in"),
        plugs.put_secure_headers,
    ]


templates = Path(__file__).parent.parent / "templates"
templates = str(templates.absolute())
loader = jinja2.FileSystemLoader(templates)
jinja_env = jinja2.Environment(loader=loader)


def render(template, **context):
    """Load a `template` and renders it with `context`.

    This is an independent function so you can call it from
    *outside* a controller.
    """
    tmpl = jinja_env.get_template(template + ".jinja2")
    return tmpl.render(**context)
