from ..errors import ConfigError
from ..helpers.imports import get_instance


MAILER = {
    "type": "proper.emails.ToConsoleMailer",
}
MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
}

def setup(app):
    config = app.config.get("MAILER", MAILER)
    validate_config(config)

    app.config.setdefault("MAILER_DEFAULT_OPTIONS", MAILER_DEFAULT_OPTIONS)
    app.mailer = get_instance(**config)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError("MAILER config must be a dictionary")
    if "type" not in config:
        raise ConfigError("MAILER config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError("MAILER['type'] must be a string or a class")
