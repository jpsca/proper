"""
Extracted from Django (http://djangoproject.com).
The original code was BSD licensed (see LICENSE)
"""
import mimetypes
import typing as t
from email import encoders, generator, message_from_string
from email.charset import QP, Charset
from email.errors import HeaderParseError
from email.header import Header
from email.headerregistry import Address, parser  # type: ignore
from email.mime.base import MIMEBase
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, getaddresses, make_msgid
from io import BytesIO, StringIO
from pathlib import Path

from .errors import InvalidEmailHeader
from .utils import DNS_NAME


utf8_charset = Charset("utf-8")
# Don't BASE64-encode UTF-8 messages so that we avoid unwanted attention from
# some spam filters.
utf8_charset_qp = Charset("utf-8")
utf8_charset_qp.body_encoding = QP

# Default MIME type to use on attachments (if it is not explicitly given
# and cannot be guessed).
DEFAULT_ATTACHMENT_MIME_TYPE = "application/octet-stream"

RFC5322_EMAIL_LINE_LENGTH_LIMIT = 998

# Header names that contain structured address data (RFC 5322).
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


def force_str(s, encoding="utf-8", errors="strict"):
    """
    Force a string to be the native type.

    Args:
        s: The string or bytes to be converted.
        encoding: The encoding to use if `s` is bytes. Defaults to "utf-8".
        errors: The error handling scheme to use for encoding errors. Defaults to "strict".

    Returns:
        The converted string.

    """
    """Force a string to be the native type"""
    if isinstance(s, str):
        return s
    return str(s, encoding, errors)


def to_list(value: t.Sequence | None) -> list:
    """
    Convert a sequence or `None` to a list.

    Args:
        value: The input value to convert.

    Returns:
        A list. If the input is None, returns an empty list.

    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def punycode(domain: str) -> str:
    """Return the Punycode of the given domain if it's non-ASCII."""
    return domain.encode("idna").decode("ascii")


def forbid_multi_line_headers(name: str, val: str, encoding: str) -> tuple[str, str]:
    """
    Forbid multi-line headers to prevent header injection.
    """
    val = str(val)  # val may be lazy
    if "\n" in val or "\r" in val:
        raise InvalidEmailHeader(
            "Header values can't contain newlines (got %r for header %r)" % (val, name)
        )
    try:
        val.encode("ascii")
    except UnicodeEncodeError:
        if name.lower() in ADDRESS_HEADERS:
            val = ", ".join(
                sanitize_address(addr, encoding) for addr in getaddresses((val,))
            )
        else:
            val = Header(val, encoding).encode()
    else:
        if name.lower() == "subject":
            val = Header(val).encode()
    return name, val


def sanitize_address(addr: str | tuple[str, str], encoding: str) -> str:
    """
    Format a pair of (name, address) or an email address string.
    """
    if isinstance(addr, tuple):
        nm, address = addr
        if "@" not in address:
            raise ValueError(f'Invalid address "{address}"')
        localpart, domain = address.rsplit("@", 1)
    else:
        addr = force_str(addr)
        try:
            token, rest = parser.get_mailbox(addr)
        except (HeaderParseError, ValueError, IndexError) as e:
            raise ValueError('Invalid address "%s"' % addr) from e
        else:
            if rest:
                # The entire email address must be parsed.
                raise ValueError(
                    'Invalid address; only %s could be parsed from "%s"' % (token, addr)
                )
            nm = token.display_name or ""
            localpart = token.local_part
            domain = token.domain or ""

    address_parts = nm + localpart + domain
    if "\n" in address_parts or "\r" in address_parts:
        raise ValueError("Invalid address; address parts cannot contain newlines.")

    # Avoid UTF-8 encode, if it's possible.
    try:
        nm.encode("ascii")
        nm = Header(nm).encode()
    except UnicodeEncodeError:
        nm = Header(nm, encoding).encode()
    try:
        localpart.encode("ascii")
    except UnicodeEncodeError:
        localpart = Header(localpart, encoding).encode()
    domain = punycode(domain)

    parsed_address = Address(username=localpart, domain=domain)
    return formataddr((nm, parsed_address.addr_spec))


class MIMEMixin:
    def as_string(self, unixfrom=False, linesep="\n"):
        """Return the entire formatted message as a string.
        Optional `unixfrom' when True, means include the Unix From_ envelope
        header.

        This overrides the default as_string() implementation to not mangle
        lines that begin with 'From '. See bug #13433 for details.
        """
        fp = StringIO()
        g = generator.Generator(fp, mangle_from_=False)
        g.flatten(self, unixfrom=unixfrom, linesep=linesep)  # type: ignore
        return fp.getvalue()

    def as_bytes(self, unixfrom=False, linesep="\n"):
        """Return the entire formatted message as bytes.
        Optional `unixfrom' when True, means include the Unix From_ envelope
        header.

        This overrides the default as_bytes() implementation to not mangle
        lines that begin with 'From '. See bug #13433 for details.
        """
        fp = BytesIO()
        g = generator.BytesGenerator(fp, mangle_from_=False)
        g.flatten(self, unixfrom=unixfrom, linesep=linesep)  # type: ignore
        return fp.getvalue()


class SafeMIMEMessage(MIMEMixin, MIMEMessage):
    def __setitem__(self, name, val):
        # message/rfc822 attachments must be ASCII
        name, val = forbid_multi_line_headers(name, val, "ascii")
        MIMEMessage.__setitem__(self, name, val)


class SafeMIMEText(MIMEMixin, MIMEText):
    def __init__(self, _text: str, _subtype: str = "plain", _charset: str = "ascii"):
        self.encoding = _charset
        MIMEText.__init__(self, _text, _subtype=_subtype, _charset=_charset)

    def __setitem__(self, name: str, val: str):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEText.__setitem__(self, name, val)

    def set_payload(self, payload, charset: Charset | str = "ascii"):
        if charset == "utf-8" and not isinstance(charset, Charset):
            has_long_lines = any(
                len(line.encode(errors="surrogateescape"))
                > RFC5322_EMAIL_LINE_LENGTH_LIMIT
                for line in payload.splitlines()
            )
            # Quoted-Printable encoding has the side effect of shortening long
            # lines, if any (#22561).
            charset = utf8_charset_qp if has_long_lines else utf8_charset
        MIMEText.set_payload(self, payload, charset=charset)


class SafeMIMEMultipart(MIMEMixin, MIMEMultipart):
    def __init__(
        self,
        _subtype: str = "mixed",
        boundary: str | None = None,
        _subparts: list[MIMEBase] | None = None,
        encoding: str = "ascii",
        **_params,
    ):
        self.encoding = encoding
        MIMEMultipart.__init__(self, _subtype, boundary, _subparts, **_params)

    def __setitem__(self, name: str, val: str):
        name, val = forbid_multi_line_headers(name, val, self.encoding)
        MIMEMultipart.__setitem__(self, name, val)


class EmailAlternative(t.TypedDict):
    mimetype: str
    content: str


class EmailAttachment(t.TypedDict, total=False):
    filename: str | None
    content: str | bytes | None
    mimetype: str | None


class EmailMessage:
    """A container for email information."""

    content_subtype: str = "plain"
    mixed_subtype: str = "mixed"
    alternative_subtype: str = "alternative"

    encoding: str
    use_localtime: bool

    def __init__(
        self,
        *,
        from_email: str,
        to: str | list[str] | tuple[str, ...] | None = None,
        bcc: str | list[str] | tuple[str, ...] | None = None,
        cc: str | list[str] | tuple[str, ...] | None = None,
        reply_to: str | list[str] | tuple[str, ...] | None = None,
        subject: str = "",
        body: str = "",
        headers: dict[str, str] | None = None,
        attachments: list[EmailAttachment | MIMEBase] | None = None,
        html: bool = False,
        encoding: str = "utf-8",
        use_localtime: bool = False,
        alternatives: list[EmailAlternative] | None = None,
        tags: dict[str, str] | None = None,
        **extra_data,
    ):
        """
        Initialize a single email message (which can be sent to multiple
        recipients).
        """
        self.to = to_list(to)
        self.cc = to_list(cc)
        self.bcc = to_list(bcc)
        self.reply_to = to_list(reply_to)

        self.from_email = from_email or ""
        self.subject = subject or ""
        self.body = body or ""

        self.attachments = []
        if attachments:
            for attachment in attachments:
                if isinstance(attachment, MIMEBase):
                    self.attach(attachment)
                elif isinstance(attachment, dict):
                    self.attach(**attachment)

        self.headers = headers or {}
        if html:
            self.content_subtype = "html"
        self.encoding = encoding
        self.use_localtime = use_localtime
        self.alternatives = alternatives or []
        self.tags = tags
        self.extra_data = extra_data

    def render(self) -> SafeMIMEText | SafeMIMEMultipart:
        msg = SafeMIMEText(self.body, self.content_subtype, self.encoding)
        msg = self._create_alternatives(msg)
        msg = self._create_attachments(msg)

        msg["Subject"] = self.subject
        msg["From"] = self.headers.get("From", self.from_email)
        self._set_list_header_if_not_empty(msg, "To", self.to)
        self._set_list_header_if_not_empty(msg, "Cc", self.cc)
        self._set_list_header_if_not_empty(msg, "Reply-To", self.reply_to)

        # Email header names are case-insensitive (RFC 2045), so we have to
        # accommodate that when doing comparisons.
        header_names = [key.lower() for key in self.headers]

        if "date" not in header_names:
            # formatdate() uses stdlib methods to format the date, which use
            # the stdlib/OS concept of a timezone, however, Django sets the
            # TZ environment variable based on the TIME_ZONE setting which
            # will get picked up by formatdate().
            msg["Date"] = formatdate(localtime=self.use_localtime)

        if "message-id" not in header_names:
            # Use cached DNS_NAME for performance
            msg["MIMEBase-ID"] = make_msgid(domain=str(DNS_NAME))

        for name, value in self.headers.items():
            # Avoid headers handled above.
            if name.lower() not in {"from", "to", "cc", "reply-to"}:
                msg[name] = value

        return msg

    def get_recipients(self) -> list[str]:
        """
        Return a list of all recipients of the email (includes direct
        addressees as well as Cc and Bcc entries).
        """
        return [email for email in (self.to + self.cc + self.bcc) if email]

    def attach_alternative(self, content: str, mimetype: str):
        """Attach an alternative content representation."""
        if content is None or mimetype is None:
            raise ValueError("Both content and mimetype must be provided.")
        self.alternatives.append(EmailAlternative(content=content, mimetype=mimetype))

    def attach(
        self,
        filename: str | MIMEBase | None = None,
        content: str | bytes | None = None,
        mimetype: str | None = None,
    ):
        """
        Attach a file with the given filename and content. The filename can
        be omitted and the mimetype is guessed, if not provided.

        If the first parameter is a MIMEBase subclass, insert it directly
        into the resulting message attachments.

        For a text/* mimetype (guessed or specified), when a bytes object is
        specified as content, decode it as UTF-8. If that fails, set the
        mimetype to DEFAULT_ATTACHMENT_MIME_TYPE and don't decode the content.
        """
        if isinstance(filename, MIMEBase):
            if content is not None or mimetype is not None:
                raise ValueError(
                    "content and mimetype must not be given when a MIMEBase "
                    "instance is provided."
                )
            self.attachments.append(filename)
        elif content is None:
            raise ValueError("content must be provided.")
        else:
            mimetype = (
                mimetype
                or filename
                and mimetypes.guess_type(filename)[0]
                or DEFAULT_ATTACHMENT_MIME_TYPE
            )
            basetype, _subtype = mimetype.split("/", 1)

            if basetype == "text":
                if isinstance(content, bytes):
                    try:
                        content = content.decode()
                    except UnicodeDecodeError:
                        # If mimetype suggests the file is text but it's
                        # actually binary, read() raises a UnicodeDecodeError.
                        mimetype = DEFAULT_ATTACHMENT_MIME_TYPE

            self.attachments.append(
                EmailAttachment(filename=filename, content=content, mimetype=mimetype)
            )

    def attach_file(self, path: str | Path, mimetype: str | None = None):
        """
        Attach a file from the filesystem.

        Set the mimetype to DEFAULT_ATTACHMENT_MIME_TYPE if it isn't specified
        and cannot be guessed.

        For a text/* mimetype (guessed or specified), decode the file's content
        as UTF-8. If that fails, set the mimetype to
        DEFAULT_ATTACHMENT_MIME_TYPE and don't decode the content.
        """
        path = Path(path)
        with path.open("rb") as file:
            content = file.read()
            self.attach(path.name, content, mimetype)

    def _create_attachments(
        self, body_msg: SafeMIMEText | SafeMIMEMultipart
    ) -> SafeMIMEText | SafeMIMEMultipart:
        if not self.attachments:
            return body_msg

        msg = SafeMIMEMultipart(_subtype=self.mixed_subtype, encoding=self.encoding)
        if self.body or body_msg.is_multipart():
            msg.attach(body_msg)
        for attachment in self.attachments:
            if isinstance(attachment, MIMEBase):
                msg.attach(attachment)
            else:
                msg.attach(self._create_attachment(*attachment))
        return msg

    def _create_alternatives(
        self, body_msg: SafeMIMEText | SafeMIMEMultipart
    ) -> SafeMIMEText | SafeMIMEMultipart:
        if not self.alternatives:
            return body_msg

        msg = SafeMIMEMultipart(_subtype=self.alternative_subtype, encoding=self.encoding)
        if self.body:
            msg.attach(body_msg)
        for alternative in self.alternatives:
            msg.attach(self._create_mime_attachment(**alternative))
        return msg

    def _create_mime_attachment(self, content: str, mimetype: str) -> MIMEBase:
        """
        Convert the content, mimetype pair into a MIME attachment object.

        If the mimetype is message/rfc822, content may be an
        email.MIMEBase or EmailMessage object, as well as a str.
        """
        basetype, subtype = mimetype.split("/", 1)
        if basetype == "text":
            attachment = SafeMIMEText(content, subtype, self.encoding)
        elif basetype == "message" and subtype == "rfc822":
            # Bug #18967: Per RFC 2046 Section 5.2.1, message/rfc822
            # attachments must not be base64 encoded.
            if isinstance(content, EmailMessage):
                # convert content into an email.MIMEBase first
                msg = content.render()
            else:
                msg = message_from_string(force_str(content))
            attachment = SafeMIMEMessage(msg, subtype)
        else:
            # Encode non-text attachments with base64.
            attachment = MIMEBase(basetype, subtype)
            attachment.set_payload(content)
            encoders.encode_base64(attachment)

        return attachment

    def _create_attachment(
        self, filename: str = "", content: str = "", mimetype: str = ""
    ) -> MIMEBase:
        """
        Convert the filename, content, mimetype triple into a MIME attachment
        object.
        """
        attachment = self._create_mime_attachment(content, mimetype)
        if filename:
            try:
                filename.encode("ascii")
                attachment.add_header(
                    "Content-Disposition", "attachment", filename=filename
                )
            except UnicodeEncodeError:
                attachment.add_header(
                    "Content-Disposition", "attachment", filename=("utf-8", "", filename)
                )

        return attachment

    def _set_list_header_if_not_empty(
        self, msg: MIMEBase, header: str, values: list[str]
    ) -> None:
        """
        Set msg's header, either from self.headers, if present, or from
        the values argument if not empty.
        """
        try:
            msg[header] = self.headers[header]
        except KeyError:
            if values:
                msg[header] = ", ".join(str(v) for v in values)
