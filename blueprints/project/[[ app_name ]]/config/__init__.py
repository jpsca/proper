import os
from importlib import import_module
from pathlib import Path

from properconf import ConfigDict


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"


def get_env(default="development"):
    env = os.getenv(ENV_VAR)
    if env:
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        return envfile.read_text().strip()
    return default


def load_config(env):
    config = ConfigDict()

    # Load env config
    env_config = import_module(f".{env}", __package__)
    config.load_module(env_config)

    # Load env secrets
    path = Path(__file__).parent
    config.load_secrets(path / env)

    return config


env = get_env()
config = load_config(env)
