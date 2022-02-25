import logging
import os
from importlib import import_module
from pathlib import Path

from .default_config import get_default_config


__all__ = ("get_env", )

logger = logging.getLogger(__name__)

ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"


def get_env(default="development"):
    env = os.getenv(ENV_VAR)
    if env:
        logger.debug("%s var found: %s", ENV_VAR, env)
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        env = envfile.read_text().strip()
        logger.debug("%s file found: %s", ENV_VAR, env)
        return env

    logger.debug("Using default environment")
    return default


def load_config(module, root_path):
    config = get_default_config()
    env = get_env()
    config_path = root_path / "config"
    config_file = config_path / f"{env}.py"
    if config_file.is_file():
        env_config = import_module(f".config.{env}", module.__package__).config
        config.update(env_config)
    else:
        logger.warning("%s cannot be imported", config_file)

    # load_credentials(config, config_path / env)
    return config
