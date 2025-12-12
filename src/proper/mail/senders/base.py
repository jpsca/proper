import email.policy
import typing as t
from datetime import datetime, timezone
from email.headerregistry import Address, AddressHeader
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from ..message import (
    DEFAULT_ATTACHMENT_MIME_TYPE,
    EmailAttachment,
    EmailMessageDict,
)
from ..utils import DNS_NAME, force_bytes, force_str, punycode


ADDRESS_HEADERS = {
    "from",
    "sender",
    "reply-to",
    "to",
    "cc",
    "bcc",
    "resent-from",
    "resent-sender",
    "resent-to",
    "resent-cc",
    "resent-bcc",
}


class BaseSender:
    """Base class for email senders implementations.

    Subclasses must at least overwrite `send_email()`.
    """

    # Undocumented charset to use for text/* message bodies and attachments.
    # If None, defaults to the message charset.
    encoding = None

    default_from: str
    fail_silently: bool
    policy: "email.policy.EmailPolicy[EmailMessage]" = email.policy.default

    def __init__(self, fail_silently: bool = False, **default_options: t.Any):
        self.default_options = default_options
        self.fail_silently = fail_silently

    def open(self, *args, **kwargs) -> bool:
        """Open a network connection.

        This method can be overwritten by mailer implementations to
        open a network connection.

        It's up to the implementation to track the status of
        a network connection if it's needed by the mailer.

        This method can be called by applications to force a single
        network connection to be used when sending mails. See the
        `_send()` method of the `SMTPSender` for a reference
        implementation.

        The default implementation does nothing.
        """
        return False

    def close(self) -> None:
        """Close a network connection.

        Like `open()`, the default implementation does nothing.
        """
        pass

    def send_email(self, *messages: EmailMessageDict) -> t.Any:
        """Sends one or more `EmailMessage` objects and returns the number of
        email messages sent.
        """
        raise NotImplementedError

    def render(self, message: EmailMessageDict) -> EmailMessage:
        msg = EmailMessage(policy=self.policy)
        self._add_bodies(msg, message)
        self._add_attachments(msg, message)

        headers = message["headers"]
        msg["Subject"] = str(message["subject"])
        msg["From"] = str(headers.get("From", message["from_email"]))
        self._set_list_header_if_not_empty(msg, headers, "To", message["to"])
        self._set_list_header_if_not_empty(msg, headers, "Cc", message["cc"])
        self._set_list_header_if_not_empty(msg, headers, "Reply-To", message["reply_to"])

        # Email header names are case-insensitive (RFC 2045), so we have to
        # accommodate that when doing comparisons.
        header_names = [key.lower() for key in headers]
        if "date" not in header_names:
            tz = timezone.utc
            msg["Date"] = datetime.now(tz)
        if "message-id" not in header_names:
            # Use cached DNS_NAME for performance
            msg["Message-ID"] = make_msgid(domain=DNS_NAME)  # type: ignore
        for name, value in headers.items():
            # Avoid headers handled above.
            if name.lower() not in {"from", "to", "cc", "reply-to"}:
                msg[name] = force_str(value, strings_only=True)
        self._idna_encode_address_header_domains(msg)
        return msg

    def _add_bodies(self, msg: EmailMessage, message: EmailMessageDict):
        if message["body"] or not message["alternatives"]:
            encoding = self.encoding or message["charset"]
            body = force_str(
                message["body"] or "",
                encoding=encoding,
                errors="surrogateescape",
            )
            msg.set_content(body, subtype=message["content_subtype"], charset=encoding)

        if message["alternatives"]:
            msg.make_alternative()
            encoding = self.encoding or message["charset"]
            for alternative in message["alternatives"]:
                maintype, subtype = alternative["mimetype"].split("/", 1)
                content = alternative["content"]
                if maintype == "text":
                    if isinstance(content, bytes):
                        content = content.decode()
                    msg.add_alternative(content, subtype=subtype, charset=encoding)
                else:
                    content = force_bytes(content, encoding=encoding, strings_only=True)
                    msg.add_alternative(content, maintype=maintype, subtype=subtype)
        return msg

    def _add_attachments(self, msg: EmailMessage, message: EmailMessageDict):
        if message["attachments"]:
            msg.make_mixed()
            for attachment in message["attachments"]:
                self._add_attachment(msg, message, attachment)

    def _add_attachment(
        self,
        msg: EmailMessage,
        message: EmailMessageDict,
        attachment: EmailAttachment
    ):
        encoding = self.encoding or message["charset"]
        maintype, subtype = attachment["mimetype"].split("/", 1)
        filename = attachment["filename"]
        content = Path(filename).read_bytes()

        if maintype == "text":
            # For a text/* mimetype, decode the file's content as UTF-8.
            # If that fails, set the mimetype to DEFAULT_ATTACHMENT_MIME_TYPE
            # and don't decode the content.
            try:
                content = content.decode()
            except UnicodeDecodeError:
                mimetype = DEFAULT_ATTACHMENT_MIME_TYPE
                maintype, subtype = mimetype.split("/", 1)

        # See email.contentmanager.set_content() docs for the cases here.
        if maintype == "text":
            # For text/*, content must be str, and maintype cannot be provided.
            msg.add_attachment(content, subtype=subtype, filename=filename, charset=encoding)
        elif maintype == "message":
            msg.add_attachment(content, subtype=subtype, filename=filename)
        else:
            msg.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

    def _set_list_header_if_not_empty(
        self,
        msg: EmailMessage,
        headers: dict[str, t.Any],
        header,
        values,
    ):
        """
        Set msg's header, either from self.extra_headers, if present, or from
        the values argument if not empty.
        """
        try:
            msg[header] = headers[header]
        except KeyError:
            if values:
                msg[header] = ", ".join(str(v) for v in values)

    def _idna_encode_address_header_domains(self, msg: EmailMessage):
        """
        If msg.policy does not permit utf8 in headers, IDNA encode all
        non-ASCII domains in its address headers.
        """
        # Avoids a problem where Python's email incorrectly converts non-ASCII
        # domains to RFC 2047 encoded-words:
        # https://github.com/python/cpython/issues/83938.
        # This applies to the domain only, not to the localpart (username).
        # There is no RFC that permits any 7-bit encoding for non-ASCII
        # characters before the '@'.
        if not getattr(msg.policy, "utf8", False):
            # Not using SMTPUTF8, so apply IDNA encoding in all address
            # headers. IDNA encoding does not alter domains that are already
            # ASCII.
            for field, value in msg.items():
                if isinstance(value, AddressHeader) and any(
                    not addr.domain.isascii() for addr in value.addresses
                ):
                    msg.replace_header(
                        field,
                        [
                            Address(
                                display_name=addr.display_name,
                                username=addr.username,
                                domain=punycode(addr.domain),
                            )
                            for addr in value.addresses
                        ],
                    )
