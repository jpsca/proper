import json
from importlib import import_module
from pathlib import Path

from whitenoise import WhiteNoise

from proper.constants import MIN_SECRET_LENGTH
from proper.helpers import Render, Serializer
from proper.static import RX_INMUTABLES_FILE


STATIC_PREFIX = "static"


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


class AppSetupMixin:
    def _setup_root_path(self, import_name):
        module = import_module(import_name)
        path = Path(module.__file__)
        if path.is_file():
            path = path.parent

        self.root_path = path.absolute()

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

    def _setup_render(self):
        self._load_static_manifest()
        self.render = Render(self.templates_path)
        self.render.globals["url_for"] = self.url_for
        self.render.globals["url_static"] = self.url_static
        self.render.globals["include_static"] = self.include_static

    def _load_static_manifest(self):
        path = self.static_manifest_path
        if not self._config.debug and path.exists():
            self.static_manifest = json.loads(path.read_text())
        else:
            self.static_manifest = {}

    def _setup_whitenoise(self):
        self._wrapped_wsgi = self.wsgi_app

        if self.public_path.exists():
            self._wrapped_wsgi = WhiteNoise(
                self.wsgi_app,
                root=self.public_path,
                prefix=STATIC_PREFIX,
                autorefresh=self._config.debug,
                immutable_file_test=RX_INMUTABLES_FILE,
            )
