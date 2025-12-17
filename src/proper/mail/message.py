import mimetypes
import typing as t
from collections.abc import Iterable
from pathlib import Path

from ..core.global_context import current
from ..helpers import textify
from .utils import to_list


# Default MIME type to use on attachments (if it is not explicitly given
# and cannot be guessed).
DEFAULT_ATTACHMENT_MIME_TYPE = "application/octet-stream"

class EmailAttachment(t.TypedDict):
    filename: str
    mimetype: str


class EmailAlternative(t.TypedDict):
    content: str
    mimetype: str


class EmailMessageDict(t.TypedDict):
    content_subtype: str
    charset: str
    from_email: str
    subject: str
    body: str
    to: list[str]
    bcc: list[str]
    cc: list[str]
    reply_to: list[str]
    headers: dict[str, t.Any]
    attachments: list[EmailAttachment]
    alternatives: list[EmailAlternative]


class EmailMessage:
    """A container for email information."""

    charset = "utf-8"
    content_subtype = "plain"

    from_email: str = ""
    subject: str = ""
    body: str = ""
    to: list[str] = None  # type: ignore
    bcc: list[str] = None  # type: ignore
    cc: list[str] = None  # type: ignore
    reply_to: list[str] = None  # type: ignore
    headers: dict[str, t.Any] = None  # type: ignore

    def __init__(
        self,
        *,
        from_email: str | None = None,
        subject: str = "",
        body: str = "",
        to: str | Iterable[str] | None = None,
        bcc: str | Iterable[str] | None = None,
        cc: str | Iterable[str] | None = None,
        reply_to: str | Iterable[str] | None = None,
        headers: dict[str, t.Any] | None = None,
    ):
        """
        Initialize a single email message (which can be sent to multiple
        recipients).
        """
        default_options = {}
        if current.app:
            default_options = current.app.config.get("MAILER_DEFAULT_OPTIONS", {})

        self.from_email = from_email or default_options.get("default_from", "")
        self.subject = subject or self.subject or default_options.get("subject", "")
        self.body = body or self.body or default_options.get("body", "")

        self.to = to_list(to or self.to or default_options.get("to"))
        self.bcc = to_list(bcc or self.bcc or default_options.get("bcc"))
        self.cc = to_list(cc or self.cc or default_options.get("cc"))
        self.reply_to = to_list(reply_to or self.reply_to or default_options.get("reply_to"))

        self.headers = {**(headers or self.headers or default_options.get("headers") or {})}

        self.attachments: list[EmailAttachment] = []
        self.alternatives: list[EmailAlternative] = []

    def attach_file(self, filename: str | Path, mimetype: str = ""):
        """
        Attach a file from the filesystem.

        Set the mimetype to DEFAULT_ATTACHMENT_MIME_TYPE if it isn't specified
        and cannot be guessed.
        """
        filename = Path(filename).resolve()
        mimetype = (
            mimetype
            or mimetypes.guess_type(filename or "")[0]
            or DEFAULT_ATTACHMENT_MIME_TYPE
        )
        self.attachments.append(EmailAttachment(filename=str(filename), mimetype=mimetype))

    def attach_alternative(self, content, mimetype):
        """Attach an alternative content representation."""
        if content is None or mimetype is None:
            raise ValueError("Both content and mimetype must be provided.")
        self.alternatives.append(EmailAlternative(content=content, mimetype=mimetype))

    def generate_text_alternative(self):
        text_content = textify(self.body)
        self.attach_alternative(text_content, "text/plain")

    def update(
        self,
        from_email: str | None = None,
        to: str | Iterable[str] | None = None,
        bcc: str | Iterable[str] | None = None,
        cc: str | Iterable[str] | None = None,
        reply_to: str | Iterable[str] | None = None,
        headers: dict[str, t.Any] | None = None,
    ):
        """Serialize the email message to a dictionary."""
        self.from_email = from_email or self.from_email
        self.to = to_list(to) if to else self.to
        self.bcc = to_list(bcc) if bcc else self.bcc
        self.cc = to_list(cc) if cc else self.cc
        self.reply_to = to_list(reply_to) if reply_to else self.reply_to
        self.headers.update(headers or {})

    def send(self, **options):
        """Send the email message immediately."""
        self.update(**options)
        current.app.mailer.send_email(
            self.serialize()
        )

    def serialize(self) -> EmailMessageDict:
        """Serialize the email message to a dictionary."""
        return {
            "charset": self.charset,
            "content_subtype": self.content_subtype,
            "from_email": self.from_email,
            "subject": self.subject,
            "body": self.body,
            "to": self.to,
            "bcc": self.bcc,
            "cc": self.cc,
            "reply_to": self.reply_to,
            "headers": self.headers,
            "alternatives": self.alternatives,
            "attachments": self.attachments,
        }

    to_dict = serialize
