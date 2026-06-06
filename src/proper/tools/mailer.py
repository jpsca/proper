from ..errors import ConfigError
from ..helpers.imports import get_instance


DEFAULT_CONFIG = {
    "MAILER": "console",
    "MAILERS": {
        "console": {"type": "proper.emails.ToConsoleMailer"},
    },
    "MAILER_DEFAULT_OPTIONS": {"from": "no-reply@example.com"},
}


class Mailers:
    """Lazily instantiate and cache configured mailers by name."""

    def __init__(self, app):
        self._app = app
        self._instances = {}

    def __getitem__(self, name):
        if name not in self._instances:
            mailers = self._app.config.get("MAILERS", {})
            if name not in mailers:
                raise ConfigError(
                    f"Unknown mailer '{name}'. "
                    f"Available mailers: {', '.join(mailers)}"
                )
            # copy: get_instance pops "type" and would mutate the config dict
            self._instances[name] = get_instance(**dict(mailers[name]))
        return self._instances[name]


def setup(app):
    for key, value in DEFAULT_CONFIG.items():
        app.config.setdefault(key, value)
    validate_config(app.config)

    app.mailers = Mailers(app)
    app.mailer = app.mailers[app.config["MAILER"]]


def validate_config(config):
    mailers = config.get("MAILERS")
    if not isinstance(mailers, dict):
        raise ConfigError("MAILERS config must be a dictionary")

    default = config.get("MAILER")
    if default not in mailers:
        raise ConfigError(f"MAILER '{default}' is not defined in MAILERS")

    for name, backend in mailers.items():
        if not isinstance(backend, dict):
            raise ConfigError(f"MAILERS['{name}'] must be a dictionary")
        if "type" not in backend:
            raise ConfigError(f"MAILERS['{name}'] must have a 'type' key")
        if not isinstance(backend["type"], (str | type)):
            raise ConfigError(f"MAILERS['{name}']['type'] must be a string or a class")
