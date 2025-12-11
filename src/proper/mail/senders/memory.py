import copy

from ..message import EmailMessage
from .base import BaseEmailSender


class ToMemoryEmailSender(BaseEmailSender):
    """An email sender for use during test Session.

    The test connection stores email messages in a dummy outbox,
    rather than sending them out on the wire.

    The dummy outbox is accessible through the outbox instance attribute.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.outbox = []

    def send_emails(self, *messages: EmailMessage):
        """Redirect messages to the dummy outbox."""
        for msg in messages:
            email_message = msg.message()
            self.outbox.append(copy.deepcopy(email_message))
        return len(messages)
