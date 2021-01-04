import json
from importlib import import_module
from pathlib import Path

from properconf import ConfigDict

from proper.constants import MIN_SECRET_LENGTH
from proper.helpers import Serializer
from proper.router import Router

from .default_config import DEFAULT_CONFIG
from .render import Render


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


TEMPLATES_FOLDER = "templates"
STATIC_FOLDER = "static/public"
STATIC_MANIFEST = "static/manifest.json"


class AppSetup:
    serializer = None
    _cached_controllers_module = None

    def __init__(self, import_name, *, config=None):
        """
        import_name (str):
            The name of the application package. Eg.: `foobar.web`.

        config (dict):
            Optional dict-like with the config.

        """
        self.router = Router()
        self.setup(config)
        self.setup_paths(import_name)
        self.setup_render()

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
    def controllers_module(self):
        if self._cached_controllers_module:
            return self._cached_controllers_module
        module = import_module(self.controllers_name)
        self._cached_controllers_module = module
        return module

    @property
    def templates_path(self):
        return self.root_path / TEMPLATES_FOLDER

    @property
    def static_path(self):
        return self.root_path.parent / STATIC_FOLDER

    @property
    def static_manifest_path(self):
        return self.root_path.parent / STATIC_MANIFEST

    def setup(self, config):
        self._config = ConfigDict(DEFAULT_CONFIG)
        self._config.update(config)
        if "secret_key" in self._config:
            self._setup_serializer()

        self.router._debug = self._config.debug

    def setup_paths(self, import_name):
        self.import_name = import_name
        self.controllers_name = f"{import_name}.controllers"

        module = import_module(import_name)
        path = Path(module.__file__)
        if path.is_file():
            path = path.parent

        self.root_path = path.absolute()

    def setup_render(self):
        self._load_static_manifest()
        self.render = Render(self.templates_path)

        self.render.env.globals["url_for"] = self.url_for
        self.render.env.globals["url_static"] = self.url_static

    def url_static(self, filename, *, host=None):
        host = host or self._config.static.host
        filename = filename.replace("..", ".").strip("/").strip("\\").strip()
        filename = self.static_manifest.get(filename, filename)
        return f"host/{filename}"

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
        if path.exists():
            self.static_manifest = json.loads(path.read_bytes())
        else:
            self.static_manifest = {}
