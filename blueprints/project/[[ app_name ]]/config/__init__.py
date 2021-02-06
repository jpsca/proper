import os
from pathlib import Path

from properconf import ConfigDict

from . import development, production, shared, staging, testing


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"
ENVIRONMENTS = {
    "development": development,
    "production": production,
    "staging": staging,
    "testing": testing,
}


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

    # Load shared config
    config.load_module(shared)

    # Load env config
    env_config = ENVIRONMENTS.get(env, production)
    config.load_module(env_config)

    # Load env secrets
    path = Path(__file__).parent
    config.load_secrets(path / env)

    return config


env = get_env()
config = load_config(env)
