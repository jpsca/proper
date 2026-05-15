import copy

from ..message import EmailMessageDict
from .base import BaseMailer


class ToMemoryMailer(BaseMailer):
    """An email sender for use during test Session.

    The test connection stores email messages in a dummy outbox,
    rather than sending them out on the wire.

    The dummy outbox is accessible through the outbox instance attribute.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.outbox = []

    def send_now(self, *messages: EmailMessageDict):
        """Redirect messages to the dummy outbox."""
        for message in messages:
            email_message = self.render(message)
            self.outbox.append(copy.deepcopy(email_message))
        return len(messages)
