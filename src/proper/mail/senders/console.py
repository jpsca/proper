"""
Extracted from Django (http://djangoproject.com).
The original code was BSD licensed (see LICENSE)
"""
import sys
import threading

from ..message import EmailMessageDict
from .base import BaseSender


class ToConsoleSender(BaseSender):
    """
    An email sender that writes messages to console instead of sending them.
    Ideal for development.
    """

    def __init__(self, *args, **kwargs):
        self.stream = kwargs.pop("stream", sys.stdout)
        self._lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def send_email(self, *messages: EmailMessageDict):
        """Write all messages to the stream in a thread-safe way."""
        if not messages:
            return
        msg_count = 0
        with self._lock:
            try:
                stream_created = self.open()
                for message in messages:
                    self.write_message(message)
                    self.stream.flush()  # flush after each message
                    msg_count += 1
                if stream_created:
                    self.close()
            except Exception:
                if not self.fail_silently:
                    raise
        return msg_count

    def write_message(self, message: EmailMessageDict):
        email_message = self.render(message)
        msg_data = email_message.as_bytes()
        charset = "utf-8"
        em_charset = email_message.get_charset()
        if em_charset:
            charset = em_charset if isinstance(em_charset, str) else em_charset.get_output_charset()
        msg_data = msg_data.decode(charset or "utf-8")
        self.stream.write("%s\n" % msg_data)
        self.stream.write("-" * 79)
        self.stream.write("\n")
