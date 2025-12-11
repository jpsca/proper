import typing as t

from ..message import EmailMessage


class BaseEmailSender:
    """Base class for email senders implementations.

    Subclasses must at least overwrite send_emails().
    """
    default_from: str
    fail_silently: bool

    def __init__(self, default_from: str = "", fail_silently: bool = False):
        self.default_from = default_from or "noreply@example.com"
        self.fail_silently = fail_silently

    def open(self, *args, **kwargs) -> bool:
        """Open a network connection.

        This method can be overwritten by mailer implementations to
        open a network connection.

        It's up to the implementation to track the status of
        a network connection if it's needed by the mailer.

        This method can be called by applications to force a single
        network connection to be used when sending mails. See the
        `_send()` method of the `SMTPEmailSender` for a reference
        implementation.

        The default implementation does nothing.
        """
        return False

    def close(self) -> None:
        """Close a network connection.

        Like `open()`, the default implementation does nothing.
        """
        pass

    def send_email(self, **kwargs) -> t.Any:
        kwargs.setdefault("from_email", self.default_from)
        return self.send_emails(EmailMessage(**kwargs))

    def send_emails(self, *messages: EmailMessage) -> t.Any:
        """Sends one or more `EmailMessage` objects and returns the number of
        email messages sent.
        """
        raise NotImplementedError
