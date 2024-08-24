import typing as t

from ..message import EmailMessage


class BaseMailer:
    """Base class for mailers implementations.

    Subclasses must at least overwrite send_messages().
    """

    def __init__(self, default_from: str | None = None, fail_silently: bool = False):
        self.default_from = default_from or "noreply@example.com"
        self.fail_silently = fail_silently

    def open(self):
        """Open a network connection.

        This method can be overwritten by mailer implementations to
        open a network connection.

        It's up to the implementation to track the status of
        a network connection if it's needed by the mailer.

        This method can be called by applications to force a single
        network connection to be used when sending mails. See the
        `send()` method of the `SMTPMailer` for a reference
        implementation.

        The default implementation does nothing.
        """
        pass

    def close(self):
        """Close a network connection.

        Like `open()`, the default implementation does nothing.
        """
        pass

    def send(self, **kwargs) -> t.Any:
        kwargs.setdefault("from_email", self.default_from)
        return self.send_messages(EmailMessage(**kwargs))

    def send_messages(self, *email_messages: EmailMessage) -> t.Any:
        """Sends one or more `EmailMessage` objects and returns the number of
        email messages sent.
        """
        raise NotImplementedError
