"""
## proper.support.configdict

"""
from pathlib import Path

import yaml

from .dot import Dot
from .secrets import read_secrets


__all__ = ("ConfigDict",)


class ConfigDict(Dot):
    """A `proper.Dot` for configuration storage.

    Has methods for loading config from YAML files and encrypted YAML files.

    """

    def _parse_content(self, _path, content):
        # could be extended to load other file formats
        config = yaml.safe_load(content) or {}
        if isinstance(config, dict):
            return config
        raise ValueError(f"Invalid config at {str(_path)}")

    def load_file(self, path):
        """Load values from a YAML file.
        """
        path = Path(path)
        if path.is_file():
            content = path.read_text()
            config = self._parse_content(path, content)
            self.update(config)
        return self

    def load_secrets(self, secrets_path):
        """Load values from a YAML file, and decrypt those values using a
        `master.key` that should be in the same folder.
        """
        secrets_path = Path(secrets_path)
        if secrets_path.is_file():
            content = read_secrets(secrets_path)
            config = self._parse_content(secrets_path, content)
            self.update(config)
        return self
