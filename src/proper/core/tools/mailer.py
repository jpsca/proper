from proper.errors import ConfigError
from proper.helpers.utils import get_instance


NAME = "MAILER"
DEFAULT_CONFIG = {
    "type": "proper.mail.ToConsoleMailer",
    "default_from": "hello@example.com",
}

def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    validate_config(config)
    app.config[NAME] = config

    app.mailer = get_instance(**config)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")

    if "default_from" not in config:
        raise ConfigError(f"{NAME} config must have a 'default_from' key")
    if not isinstance(config["default_from"], str):
        raise ConfigError(f"{NAME}['default_from'] must be a string")
