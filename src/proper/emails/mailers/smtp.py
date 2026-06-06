"""
Extracted from Django (http://djangoproject.com).
The original code was BSD licensed (see LICENSE)
"""

import email.policy
import smtplib
import ssl
import threading
import typing as t
from email.headerregistry import Address, AddressHeader
from functools import cached_property
from os import PathLike

from ..message import EmailMessageDict
from ..utils import DNS_NAME, force_str, punycode
from .base import BaseMailer


StrOrBytesPath: t.TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]


class SMTPMailer(BaseMailer):
    """
    An email sender that manages the SMTP network connection.
    """

    policy = email.policy.SMTP
    connection: smtplib.SMTP_SSL | smtplib.SMTP | None = None

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        timeout: float | None = None,
        ssl_keyfile: StrOrBytesPath | None = None,
        ssl_certfile: StrOrBytesPath | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.ssl_keyfile = ssl_keyfile
        self.ssl_certfile = ssl_certfile

        if self.use_ssl and self.use_tls:
            raise ValueError(
                "EMAIL_USE_TLS/EMAIL_USE_SSL are mutually exclusive, so only set "
                "one of those settings to True."
            )
        self.connection = None
        self._lock = threading.RLock()

    @property
    def connection_class(self):
        return smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

    @cached_property
    def ssl_context(self):
        if self.ssl_certfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        else:
            return ssl.create_default_context()

    def open(self, local_hostname: str = "") -> bool:
        """
        Ensure an open connection to the email server. Return whether or not a
        new connection was required (True or False) or None if an exception
        passed silently.
        """
        if self.connection:
            # Nothing to do if the connection is already open.
            return False

        # If local_hostname is not specified, socket.getfqdn() gets used.
        # For performance, we use the cached FQDN for local_hostname.
        connection_params: dict[str, t.Any] = {
            "local_hostname": local_hostname or DNS_NAME.get_fqdn()
        }
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        if self.use_ssl:
            connection_params["context"] = self.ssl_context
        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )

            # TLS/SSL are mutually exclusive, so only attempt TLS over
            # non-secure connections.
            if not self.use_ssl and self.use_tls:
                self.connection.starttls(context=self.ssl_context)
            if self.username and self.password:
                self.connection.login(self.username, self.password)
        except OSError:
            if not self.fail_silently:
                raise
        return True

    def close(self):
        """Close the connection to the email server."""
        if self.connection is None:
            return
        try:
            try:
                self.connection.quit()
            except (ssl.SSLError, smtplib.SMTPServerDisconnected):
                # This happens when calling quit() on a TLS connection
                # sometimes, or when the connection was already disconnected
                # by the server.
                self.connection.close()
            except smtplib.SMTPException:
                if self.fail_silently:
                    return
                raise
        finally:
            self.connection = None

    def send_now(self, *messages: EmailMessageDict) -> int:
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not messages:
            return 0
        with self._lock:
            new_conn_created = self.open()
            if not self.connection or new_conn_created is None:
                # We failed silently on open().
                # Trying to send would be pointless.
                return 0
            num_sent = 0
            try:
                for message in messages:
                    sent = self._send(message)
                    if sent:
                        num_sent += 1
            finally:
                if new_conn_created:
                    self.close()
        return num_sent

    def _send(self, message: EmailMessageDict) -> bool:
        """A helper method that does the actual sending."""
        assert self.connection is not None
        recipients = [email for email in (message["to"] + message["cc"] + message["bcc"]) if email]
        if not recipients:
            return False
        from_email = self.prep_address(message["from_email"])
        recipients = [self.prep_address(addr) for addr in recipients]
        email_message = self.render(message)
        try:
            self.connection.sendmail(from_email, recipients, email_message.as_bytes())
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
            return False
        return True

    def prep_address(self, address, force_ascii=True):
        """
        Return the addr-spec portion of an email address. Raises ValueError for
        invalid addresses, including CR/NL injection.

        If force_ascii is True, apply IDNA encoding to non-ASCII domains, and
        raise ValueError for non-ASCII local-parts (which can't be encoded).
        Otherwise, leave Unicode characters unencoded (e.g., for sending with
        SMTPUTF8).
        """
        address = force_str(address)
        parsed = AddressHeader.value_parser(address)
        defects = {str(defect) for defect in parsed.all_defects}
        # Django allows local mailboxes like "From: webmaster" (#15042).
        defects.discard("addr-spec local part with no domain")
        # A non-ASCII local-part is valid with SMTPUTF8, so don't treat the
        # parser's defect as a hard error; whether to allow it is decided
        # explicitly below via `force_ascii`. CPython stopped emitting this
        # defect in 3.15 (https://github.com/python/cpython/issues/81074), so
        # we can't rely on it being present either.
        defects.discard("local-part contains non-ASCII characters)")
        if defects:
            raise ValueError(f"Invalid address {address!r}: {'; '.join(defects)}")

        mailboxes = parsed.all_mailboxes
        if len(mailboxes) != 1:
            raise ValueError(f"Invalid address {address!r}: must be a single address")

        mailbox = mailboxes[0]
        if force_ascii and mailbox.local_part and not mailbox.local_part.isascii():
            # A non-ASCII local-part can't be IDNA-encoded (only the domain
            # can); it's only sendable with SMTPUTF8, i.e. force_ascii=False.
            raise ValueError(
                f"Invalid address {address!r}: local-part contains non-ASCII characters"
            )
        if force_ascii and mailbox.domain and not mailbox.domain.isascii():
            # Re-compose an addr-spec with the IDNA encoded domain.
            domain = punycode(mailbox.domain)
            return str(Address(username=mailbox.local_part, domain=domain))
        else:
            return mailbox.addr_spec
