import json
from importlib import import_module
from pathlib import Path

from jinja2 import Markup
from properconf import ConfigDict
from whitenoise import WhiteNoise

from proper.constants import MIN_SECRET_LENGTH
from proper.helpers import Render, Serializer
from proper.router import Router
from proper.static import RX_INMUTABLES_FILE
from .cli import get_app_cli
from .default_config import DEFAULT_CONFIG


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


TEMPLATES_FOLDER = "templates"
STATIC_PREFIX = "static"
STATIC_FOLDER = "static"
PUBLIC_FOLDER = "public"
MANIFEST_PATH = "cache_manifest.json"


class SetupMixin:
    serializer = None

    def __init__(self, import_name, *, config=None):
        """
        import_name (str):
            The name of the application package. Eg.: `foobar.web`.

        config (dict):
            Optional dict-like with the config.

        """
        self.cli = get_app_cli(self)()
        self.router = Router()
        self.setup(config)
        self.setup_root_path(import_name)
        self.setup_render()
        self._wrap_wsgi_app()

    @property
    def config(self):
        return self._config

    @property
    def routes(self):
        return self.router._routes

    @routes.setter
    def routes(self, values):
        self.router.routes = values

    @property
    def templates_path(self):
        return self.root_path / TEMPLATES_FOLDER

    @property
    def static_path(self):
        return self.root_path.parent / STATIC_FOLDER

    @property
    def public_path(self):
        return self.static_path / PUBLIC_FOLDER

    @property
    def static_manifest_path(self):
        return self.static_path / MANIFEST_PATH

    def setup(self, config):
        self._config = ConfigDict(DEFAULT_CONFIG)
        self._config.update(config)
        if "secret_key" in self._config:
            self._setup_serializer()

        self.router._debug = self._config.debug

    def setup_root_path(self, import_name):
        module = import_module(import_name)
        path = Path(module.__file__)
        if path.is_file():
            path = path.parent

        self.root_path = path.absolute()

    def setup_render(self):
        self._load_static_manifest()
        self.render = Render(self.templates_path)
        self.render.globals["url_for"] = self.url_for
        self.render.globals["url_static"] = self.url_static
        self.render.globals["include_static"] = self.include_static

    def url_static(self, filename, *, host=None):
        host = host or self._config.static.host or f"/{STATIC_PREFIX}"
        filename = filename.replace("..", ".").strip("/").strip("\\").strip()
        filename = self.static_manifest.get(filename, filename)
        return f"{host}/{filename}"

    def include_static(self, filename):
        """Read and returns a text file from the `static/public` folder, to include
        in the template as-is.
        """
        text = (self.public_path / filename).read_text()
        return Markup(text)

    def get_serializer(self):
        if not self.serializer:
            self._setup_serializer()
        return self.serializer

    # Private

    def _setup_serializer(self):
        secret_key = self._get_secret_key()
        self.serializer = Serializer(secret_key)

    def _get_secret_key(self):
        secret_key = self._config.get("secret_key")

        if secret_key is None:
            raise MissingSecretKey(
                'Please add a "secret_key" to your secrets.\n'
                "Your secret key is needed for verifying the integrity of "
                "signed cookies. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks. \n"
                "You can use `proper secret` to generate a secure secret key."
            )

        secret_key = str(secret_key)
        if len(secret_key) < MIN_SECRET_LENGTH:
            raise BadSecretKey(
                "Your secret_key, used for verifying the integrity of "
                "signed cookies, is not secure enough. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks. \n"
                "You can use `proper secret` to generate a secure secret key."
            )

        return secret_key

    def _load_static_manifest(self):
        path = self.static_manifest_path
        if not self._config.debug and path.exists():
            self.static_manifest = json.loads(path.read_text())
        else:
            self.static_manifest = {}

    def _wrap_wsgi_app(self):
        self._wrapped_wsgi = self.wsgi_app

        if self.public_path.exists():
            self._wrapped_wsgi = WhiteNoise(
                self.wsgi_app,
                root=self.public_path,
                prefix=STATIC_PREFIX,
                autorefresh=self._config.debug,
                immutable_file_test=RX_INMUTABLES_FILE,
            )
