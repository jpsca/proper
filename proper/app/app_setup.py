from importlib import import_module
from pathlib import Path
from proper_config import ConfigDict

from proper.constants import MIN_SECRET_LENGTH
from proper.errors import MatchNotFound, MethodNotAllowed
from proper.support import Serializer
from proper.router import Router

from .default_config import DEFAULT_CONFIG


class AppSetup(object):
    serializer = None

    def __init__(
        self,
        import_name,
        *,
        config=None,
        controllers_name="controllers",
    ):
        """
            import_name (str):
                The name of the application package. Eg.: `foobar.web`.

            config (dict, path, list of paths and/or dicts, or None):
                Config file(s) or dict(s)

            controllers_name (str):
                Optional.
                The name of the controllers module, relative to `import_name`.

        """
        self.import_name = import_name
        self.controllers_name = f"{import_name}.{controllers_name}"
        self._cached_controllers_module = None
        self.router = Router(MatchNotFound=MatchNotFound, MethodNotAllowed=MethodNotAllowed)
        self._set_root_path()
        self.setup(*_be_a_list(config))

    def _set_root_path(self):
        module = import_module(self.import_name)
        path = Path(module.__file__)
        if path.is_file():
            path = path.parent
        self.root_path = path

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
            return self.__cached_controllers_module
        module = import_module(self.controllers_name)
        self.__cached_controllers_module = module
        return module

    def load_config(self, *config):
        for file_or_dict in config:
            if isinstance(file_or_dict, dict):
                self._config.update(file_or_dict)
            else:
                self._config.load_file(file_or_dict)

    def setup(self, *config):
        self._config = ConfigDict(DEFAULT_CONFIG)
        self.load_config(*config)
        self.config_router()
        if "secret_key" in self.config:
            self.init_serializer()

    def config_router(self):
        self.router.host = self._config.get("default_host", "localhost")
        self.router.root_path = self._config.get("root_path", "")
        self.router.use_ssl = self._config.get("use_ssl", False)
        self.router._debug = self.config.debug

    def get_serializer(self):
        if not self.serializer:
            self.init_serializer()
        return self.serializer

    def init_serializer(self):
        secret_key = self.get_secret_key()
        self.serializer = Serializer(secret_key)

    def url_for(self, name, *, _external=False, _anchor=None, **kwargs):
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, _external=_external, _anchor=_anchor, **kwargs)

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


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


def _be_a_list(something):
    if something is None:
        return []
    if isinstance(something, (list, tuple)):
        return something
    return [something]
