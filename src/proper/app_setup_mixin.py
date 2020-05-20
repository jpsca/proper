from pathlib import Path
from proper_config import ConfigDict

from .constants import MIN_SECRET_LENGTH
from .default_config import DEFAULT_CONFIG
from .router import Router
from .support import Serializer


class AppSetupMixin(object):
    serializer = None

    def __init__(
        self,
        root=None,
        *,
        debug=False,
        config=None,
        secrets=None,
        _controllers="controllers",
    ):
        """
            root (str):
                The root path of your application

            config (dict, path, list of paths and/or dicts, or None):
                Config file(s)

            secrets (dict, path, list of paths and/or dicts, or None):
                Encrypted secrets file(s)

            _controllers (str):
                Name of the module with the controllers, relative to the
                root of your application.

        """
        self.debug = debug
        self._set_root(root)
        self._set_controllers_mod(_controllers)
        self._config = ConfigDict(DEFAULT_CONFIG)
        self.router = Router()
        self.setup(config=config, secrets=secrets)

    @property
    def config(self):
        return self._config

    def _set_root(self, root):
        root = Path(root)
        if root.is_file():
            root = root.parent
        self.root = root

    def _set_controllers_mod(self, controllers):
        self.controllers_mod = self.root.name + "." + controllers

    def setup(self, config=None, *, secrets=None):
        self.load_config(_be_a_list(config), _be_a_list(secrets))
        self.config_router()
        if "secret_key" in self.config:
            self.init_serializer()

    def load_config(self, config=None, secrets=None):
        for file_or_dict in config:
            if isinstance(file_or_dict, dict):
                self._config.update(file_or_dict)
            else:
                self._config.load_file(file_or_dict)

        for file_or_dict in secrets:
            self._config.load_secrets(file_or_dict)

    def config_router(self):
        self.router.host = self._config.get("default_host", "localhost")
        self.router.root_path = self._config.get("root_path", "")
        self.router.use_ssl = self._config.get("use_ssl", False)
        self.router._debug = self.debug

    def init_serializer(self):
        secret_key = self.get_secret_key()
        self.serializer = Serializer(secret_key)

    def get_secret_key(self):
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

    def get_serializer(self):
        if not self.serializer:
            self.init_serializer()
        return self.serializer


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


class ControllersNotFound(Exception):
    pass


def _be_a_list(something):
    if something is None:
        return []
    if isinstance(something, (list, tuple)):
        return something
    return [something]
