import os
from pathlib import Path

from properconf import ConfigDict


def load_config(env):
    root_path = Path(__file__).parent
    config = ConfigDict()
    config.load_file(root_path / "shared.toml")
    config.load_file(root_path / env / "config.toml")
    config.load_secrets(root_path / env / "secrets.enc.toml")
    return config


env = os.getenv("APP_ENV", "development")
config = load_config(env)
