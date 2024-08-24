"""
Mailer that writes messages to a file.

Extracted from Django (http://djangoproject.com).
The original code was BSD licensed (see LICENSE)
"""
import datetime
import os
from pathlib import Path

from .console import ToConsoleMailer


class ToFileMailer(ToConsoleMailer):
    def __init__(self, path: Path | str, multifile: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Since we're using the console-based backend as a base,
        # force the stream to be initally None, so we don't default to stdout
        self.stream = None

        path = Path(path).absolute()
        if path.is_file():
            path = path.parent

        # Try to create it, if it not exists.
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(
                "Could not create directory for saving email"
                " messages: %s (%s)" % (path, e)
            ) from e

        # Make sure that `path` exists and is writable.
        assert path.is_dir()
        assert os.access(path, os.W_OK), f"{path} is not writable"

        self.multifile = multifile
        self.path = path
        self._filepath: Path | None = None

    def _get_file(self) -> Path:
        """Return a unique file name."""
        if self._filepath is None:
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            ms = now.microsecond
            fname = "%s-%s-%s.log" % (timestamp, abs(id(self)), ms)
            self._filepath = self.path / fname

        return self._filepath

    def open(self):
        if self.stream is None:
            self.stream = self._get_file().open(mode="a")
            return True
        return self.multifile

    def close(self):
        try:
            if self.stream is not None:
                self.stream.close()
        finally:
            self.stream = None
            if self.multifile:
                self._filepath = None
