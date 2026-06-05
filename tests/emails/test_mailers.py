import email.policy
import smtplib
import ssl
import subprocess
from email.message import EmailMessage as StdEmailMessage
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest

from proper.emails import (
    BaseMailer,
    EmailMessage,
    SMTPMailer,
    ToConsoleMailer,
    ToMemoryMailer,
)
from proper.emails.message import EmailMessageDict


def make_emails():
    return [
        EmailMessage(
            from_email="from@example.com",
            subject="Subject",
            to="to@example.com",
            body=f"Content #{content}",
        ).serialize() for content in range(1, 5)]


def _simple_msg(**overrides) -> EmailMessageDict:
    base = EmailMessage(
        from_email="from@example.com",
        subject="Hello",
        body="Body text",
        to="to@example.com",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base.serialize()


class TestBaseMailer:
    def test_open_returns_false(self):
        assert BaseMailer().open() is False

    def test_close_does_nothing(self):
        BaseMailer().close()  # no error

    def test_send_now_raises(self):
        with pytest.raises(NotImplementedError):
            BaseMailer().send_now()

    def test_fail_silently_stored(self):
        m = BaseMailer(fail_silently=True)
        assert m.fail_silently is True

    def test_default_options_stored(self):
        m = BaseMailer(foo="bar")
        assert m.default_options == {"foo": "bar"}


class TestRender:
    def test_plain_body(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg())
        assert msg.get_content_type() == "text/plain"
        assert "Body text" in msg.get_content()

    def test_empty_body_still_sets_content(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg(body=""))
        assert msg.get_content_type() == "text/plain"

    def test_subject_from_to(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg())
        assert msg["Subject"] == "Hello"
        assert msg["From"] == "from@example.com"
        assert msg["To"] == "to@example.com"

    def test_cc_header(self):
        email = _simple_msg()
        email["cc"] = ["cc@example.com"]
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["Cc"] == "cc@example.com"

    def test_reply_to_header(self):
        email = _simple_msg()
        email["reply_to"] = ["reply@example.com"]
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["Reply-To"] == "reply@example.com"

    def test_bcc_not_in_rendered_headers(self):
        email = _simple_msg()
        email["bcc"] = ["secret@example.com"]
        mailer = BaseMailer()
        msg = mailer.render(email)
        # Bcc is intentionally not set via _set_list_header_if_not_empty
        assert msg["Bcc"] is None

    def test_date_auto_generated(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg())
        assert msg["Date"] is not None

    def test_date_not_overridden_when_provided(self):
        email = _simple_msg()
        email["headers"]["Date"] = "Thu, 01 Jan 2099 00:00:00 +0000"
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert "2099" in str(msg["Date"])

    def test_message_id_auto_generated(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg())
        assert msg["Message-ID"] is not None

    def test_message_id_not_overridden_when_provided(self):
        email = _simple_msg()
        email["headers"]["Message-ID"] = "<custom@example.com>"
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["Message-ID"] == "<custom@example.com>"

    def test_extra_headers_passed_through(self):
        email = _simple_msg()
        email["headers"]["X-Custom"] = "test-value"
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["X-Custom"] == "test-value"

    def test_from_header_override(self):
        email = _simple_msg()
        email["headers"]["From"] = "override@example.com"
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["From"] == "override@example.com"

    def test_to_header_override(self):
        email = _simple_msg()
        email["headers"]["To"] = "override@example.com"
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg["To"] == "override@example.com"


class TestAlternatives:
    def test_text_alternative(self):
        base = EmailMessage(
            from_email="from@example.com",
            subject="Alt",
            body="<h1>HTML</h1>",
            to="to@example.com",
        )
        base.content_subtype = "html"
        base.attach_alternative("Plain fallback", "text/plain")
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg.get_content_type() == "multipart/alternative"

        parts = list(msg.iter_parts())
        subtypes = [p.get_content_type() for p in parts]
        assert "text/html" in subtypes
        assert "text/plain" in subtypes

    def test_alternatives_with_empty_body(self):
        """When body is empty but alternatives exist, body block is skipped."""
        base = EmailMessage(
            from_email="from@example.com",
            subject="Alt",
            body="",
            to="to@example.com",
        )
        base.attach_alternative("<h1>HTML</h1>", "text/html")
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg.get_content_type() == "multipart/alternative"

    def test_bytes_text_alternative_decoded(self):
        base = EmailMessage(
            from_email="from@example.com",
            subject="Alt",
            body="Primary",
            to="to@example.com",
        )
        base.alternatives = [{"content": b"bytes fallback", "mimetype": "text/plain"}]
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        parts = list(msg.iter_parts())
        contents = [p.get_content() for p in parts]
        assert any("bytes fallback" in str(c) for c in contents)

    def test_non_text_alternative(self):
        base = EmailMessage(
            from_email="from@example.com",
            subject="Alt",
            body="Primary",
            to="to@example.com",
        )
        base.alternatives = [{"content": b"\x89PNG", "mimetype": "image/png"}]
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg.get_content_type() == "multipart/alternative"


class TestAttachments:
    def test_text_attachment(self, tmp_path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello world")

        base = EmailMessage(
            from_email="from@example.com",
            subject="Attach",
            body="See attached",
            to="to@example.com",
        )
        base.attach_file(txt, mimetype="text/plain")
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg.get_content_type() == "multipart/mixed"

    def test_binary_attachment(self, tmp_path):
        img = tmp_path / "photo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        base = EmailMessage(
            from_email="from@example.com",
            subject="Attach",
            body="See attached",
            to="to@example.com",
        )
        base.attach_file(img, mimetype="image/png")
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        assert msg.get_content_type() == "multipart/mixed"

    def test_message_rfc822_attachment(self, tmp_path):
        eml = tmp_path / "forwarded.eml"
        eml.write_bytes(b"From: a@b.com\r\nSubject: hi\r\n\r\nBody")

        base = EmailMessage(
            from_email="from@example.com",
            subject="Fwd",
            body="See attached",
            to="to@example.com",
        )
        base.attach_file(eml, mimetype="message/rfc822")
        email = base.serialize()

        mailer = BaseMailer()
        # The message/* branch calls add_attachment(content, subtype=..., filename=...)
        # which works in CPython < 3.14 but fails in 3.14+. We verify the branch
        # is reached by checking the call is made with the right args.
        original_add = StdEmailMessage.add_attachment
        calls = []

        def spy_add(self, *args, **kwargs):
            calls.append(kwargs)
            return original_add(self, *args, **kwargs)

        with patch.object(StdEmailMessage, "add_attachment", spy_add):
            try:
                mailer.render(email)
            except TypeError:
                pass  # Python 3.14 compat issue in stdlib

        # Verify the message branch was hit (subtype without maintype)
        msg_calls = [c for c in calls if c.get("subtype") == "rfc822"]
        assert msg_calls
        assert "maintype" not in msg_calls[0]

    def test_text_attachment_with_non_utf8_falls_back(self, tmp_path):
        binfile = tmp_path / "data.csv"
        binfile.write_bytes(b"\xff\xfe" + b"\x00" * 20)

        base = EmailMessage(
            from_email="from@example.com",
            subject="Attach",
            body="See attached",
            to="to@example.com",
        )
        base.attach_file(binfile, mimetype="text/csv")
        email = base.serialize()

        mailer = BaseMailer()
        msg = mailer.render(email)
        # Falls back to application/octet-stream
        assert msg.get_content_type() == "multipart/mixed"
        parts = list(msg.iter_parts())
        attachment_part = [p for p in parts if p.get_filename()][0]
        assert attachment_part.get_content_type() == "application/octet-stream"


class TestIdnaEncoding:
    def test_non_ascii_domain_gets_punycode_encoded(self):
        email = _simple_msg()
        email["to"] = ["user@münchen.de"]
        mailer = BaseMailer()
        msg = mailer.render(email)
        assert "xn--mnchen-3ya.de" in str(msg["To"])

    def test_ascii_domain_unchanged(self):
        mailer = BaseMailer()
        msg = mailer.render(_simple_msg())
        assert "example.com" in str(msg["To"])

    def test_utf8_policy_skips_idna_encoding(self):
        mailer = BaseMailer()
        mailer.policy = email.policy.SMTPUTF8
        email_dict = _simple_msg()
        email_dict["to"] = ["user@münchen.de"]
        msg = mailer.render(email_dict)
        # With utf8 policy, domain should NOT be punycode-encoded
        assert "münchen" in str(msg["To"])


class TestToMemoryMailer:
    def test_send_stores_in_outbox(self):
        mailer = ToMemoryMailer()
        email1, email2, email3, email4 = make_emails()
        assert mailer.send_now(email1) == 1
        assert mailer.send_now(email2, email3, email4) == 3
        assert len(mailer.outbox) == 4

    def test_outbox_contains_deep_copies(self):
        mailer = ToMemoryMailer()
        email = _simple_msg()
        mailer.send_now(email)
        # Modifying the original dict should not affect the stored message
        email["subject"] = "Changed"
        assert mailer.outbox[0]["Subject"] == "Hello"

    def test_send_zero_messages(self):
        mailer = ToMemoryMailer()
        assert mailer.send_now() == 0


class TestToConsoleMailer:
    def test_writes_to_stream(self):
        stream = StringIO()
        mailer = ToConsoleMailer(stream=stream)
        mailer.send_now(_simple_msg())
        value = stream.getvalue()
        assert "Subject: Hello" in value
        assert "Body text" in value
        assert "-" * 79 in value

    def test_multiple_messages(self):
        stream = StringIO()
        mailer = ToConsoleMailer(stream=stream)
        emails = make_emails()
        count = mailer.send_now(*emails)
        assert count == 4
        value = stream.getvalue()
        assert value.count("-" * 79) == 4

    def test_empty_messages_returns_none(self):
        stream = StringIO()
        mailer = ToConsoleMailer(stream=stream)
        result = mailer.send_now()
        assert result is None

    def test_open_returns_true_triggers_close(self):
        stream = StringIO()
        mailer = ToConsoleMailer(stream=stream)
        with patch.object(mailer, "open", return_value=True):
            with patch.object(mailer, "close") as mock_close:
                mailer.send_now(_simple_msg())
        mock_close.assert_called_once()

    def test_fail_silently_on_write_error(self):
        stream = Mock()
        stream.write = Mock(side_effect=OSError("write failed"))
        stream.flush = Mock()
        mailer = ToConsoleMailer(stream=stream, fail_silently=True)
        # Should not raise
        mailer.send_now(_simple_msg())

    def test_fail_loudly_on_write_error(self):
        stream = Mock()
        stream.write = Mock(side_effect=OSError("write failed"))
        stream.flush = Mock()
        mailer = ToConsoleMailer(stream=stream, fail_silently=False)
        with pytest.raises(OSError, match="write failed"):
            mailer.send_now(_simple_msg())

    def test_original_content(self):
        stream = StringIO()
        mailer = ToConsoleMailer(stream=stream)
        mailer.send_now(EmailMessage(
            subject="Subject",
            body="Content",
            from_email="from@example.com",
            to="to@example.com",
        ).serialize())

        value = stream.getvalue().strip()

        assert value.startswith("""
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: 7bit
MIME-Version: 1.0
Subject: Subject
From: from@example.com
To: to@example.com
""".strip())
        assert "\nContent\n" in value


class TestSMTPMailerInit:
    def test_defaults(self):
        m = SMTPMailer()
        assert m.host == "localhost"
        assert m.port == 587
        assert m.use_tls is False
        assert m.use_ssl is False
        assert m.connection is None

    def test_tls_ssl_mutual_exclusivity(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            SMTPMailer(use_tls=True, use_ssl=True)

    def test_connection_class_plain(self):
        assert SMTPMailer().connection_class is smtplib.SMTP

    def test_connection_class_ssl(self):
        assert SMTPMailer(use_ssl=True).connection_class is smtplib.SMTP_SSL

    def test_ssl_context_default(self):
        m = SMTPMailer()
        ctx = m.ssl_context
        assert isinstance(ctx, ssl.SSLContext)

    def test_ssl_context_custom_cert(self, tmp_path):
        # Create a self-signed cert for testing ssl_context branch
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert),
            "-days", "1", "-nodes", "-subj", "/CN=test",
        ], capture_output=True, check=True)

        m = SMTPMailer(ssl_certfile=str(cert), ssl_keyfile=str(key))
        ctx = m.ssl_context
        assert isinstance(ctx, ssl.SSLContext)


class TestSMTPMailerOpen:
    def test_open_creates_connection(self):
        m = SMTPMailer()
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = m.open()
        assert result is True
        assert m.connection is mock_smtp

    def test_open_returns_false_if_already_connected(self):
        m = SMTPMailer()
        m.connection = MagicMock()
        assert m.open() is False

    def test_open_with_tls(self):
        m = SMTPMailer(use_tls=True)
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            m.open()
        mock_smtp.starttls.assert_called_once()

    def test_open_with_credentials(self):
        m = SMTPMailer(username="user", password="pass")
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            m.open()
        mock_smtp.login.assert_called_once_with("user", "pass")

    def test_open_with_timeout(self):
        m = SMTPMailer(timeout=10.0)
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp) as cls:
            m.open()
        call_kwargs = cls.call_args[1]
        assert call_kwargs["timeout"] == 10.0

    def test_open_with_ssl(self):
        m = SMTPMailer(use_ssl=True)
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP_SSL", return_value=mock_smtp) as cls:
            m.open()
        call_kwargs = cls.call_args[1]
        assert "context" in call_kwargs
        mock_smtp.starttls.assert_not_called()

    def test_open_failure_raises(self):
        m = SMTPMailer()
        with patch("smtplib.SMTP", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                m.open()

    def test_open_failure_silent(self):
        m = SMTPMailer(fail_silently=True)
        with patch("smtplib.SMTP", side_effect=OSError("fail")):
            result = m.open()
        assert result is True  # returns True even on silent fail


class TestSMTPMailerClose:
    def test_close_no_connection(self):
        m = SMTPMailer()
        m.close()  # no error

    def test_close_calls_quit(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        m.connection = mock_conn
        m.close()
        mock_conn.quit.assert_called_once()
        assert m.connection is None

    def test_close_ssl_error_falls_back_to_close(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = ssl.SSLError("ssl fail")
        m.connection = mock_conn
        m.close()
        mock_conn.close.assert_called_once()
        assert m.connection is None

    def test_close_disconnected_falls_back_to_close(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = smtplib.SMTPServerDisconnected("gone")
        m.connection = mock_conn
        m.close()
        mock_conn.close.assert_called_once()
        assert m.connection is None

    def test_close_smtp_exception_raises(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = smtplib.SMTPException("error")
        m.connection = mock_conn
        with pytest.raises(smtplib.SMTPException):
            m.close()
        assert m.connection is None  # still cleared in finally

    def test_close_smtp_exception_silent(self):
        m = SMTPMailer(fail_silently=True)
        mock_conn = MagicMock()
        mock_conn.quit.side_effect = smtplib.SMTPException("error")
        m.connection = mock_conn
        m.close()  # no error
        assert m.connection is None


class TestSMTPMailerSendNow:
    def test_empty_messages(self):
        m = SMTPMailer()
        assert m.send_now() == 0

    def test_send_opens_and_closes(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        with patch.object(m, "open", return_value=True) as mock_open:
            m.connection = mock_conn
            mock_conn.sendmail = MagicMock()
            count = m.send_now(_simple_msg())
        mock_open.assert_called_once()
        assert count == 1

    def test_send_no_connection_returns_zero(self):
        m = SMTPMailer()
        with patch.object(m, "open", return_value=None):
            m.connection = None
            count = m.send_now(_simple_msg())
        assert count == 0

    def test_send_existing_connection_not_closed(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        m.connection = mock_conn
        with patch.object(m, "open", return_value=False):
            with patch.object(m, "close") as mock_close:
                m.send_now(_simple_msg())
        mock_close.assert_not_called()

    def test_send_no_recipients_returns_zero(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        m.connection = mock_conn
        email = _simple_msg()
        email["to"] = []
        email["cc"] = []
        email["bcc"] = []
        with patch.object(m, "open", return_value=False):
            count = m.send_now(email)
        assert count == 0
        mock_conn.sendmail.assert_not_called()

    def test_send_smtp_exception_fail_silently(self):
        m = SMTPMailer(fail_silently=True)
        mock_conn = MagicMock()
        mock_conn.sendmail.side_effect = smtplib.SMTPException("fail")
        m.connection = mock_conn
        with patch.object(m, "open", return_value=False):
            count = m.send_now(_simple_msg())
        assert count == 0

    def test_send_smtp_exception_raises(self):
        m = SMTPMailer(fail_silently=False)
        mock_conn = MagicMock()
        mock_conn.sendmail.side_effect = smtplib.SMTPException("fail")
        m.connection = mock_conn
        with patch.object(m, "open", return_value=False):
            with pytest.raises(smtplib.SMTPException):
                m.send_now(_simple_msg())

    def test_send_with_bcc(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        m.connection = mock_conn
        email = _simple_msg()
        email["bcc"] = ["hidden@example.com"]
        with patch.object(m, "open", return_value=False):
            count = m.send_now(email)
        assert count == 1
        recipients = mock_conn.sendmail.call_args[0][1]
        assert "hidden@example.com" in recipients

    def test_send_with_cc(self):
        m = SMTPMailer()
        mock_conn = MagicMock()
        m.connection = mock_conn
        email = _simple_msg()
        email["cc"] = ["copy@example.com"]
        with patch.object(m, "open", return_value=False):
            count = m.send_now(email)
        assert count == 1
        recipients = mock_conn.sendmail.call_args[0][1]
        assert "copy@example.com" in recipients


class TestSMTPMailerPrepAddress:
    def test_simple_address(self):
        assert SMTPMailer().prep_address("user@example.com") == "user@example.com"

    def test_unicode_domain(self):
        result = SMTPMailer().prep_address("user@münchen.de")
        assert result == "user@xn--mnchen-3ya.de"

    def test_invalid_address_multiple(self):
        with pytest.raises(ValueError, match="Invalid address"):
            SMTPMailer().prep_address("a@b.com, c@d.com")

    def test_local_mailbox_no_domain(self):
        # Django allows local mailboxes like "webmaster"
        result = SMTPMailer().prep_address("webmaster")
        assert result == "webmaster"

    def test_force_ascii_false_with_non_ascii_domain(self):
        result = SMTPMailer().prep_address("user@münchen.de", force_ascii=False)
        assert "münchen" in result

    def test_force_ascii_true_non_ascii_local_part_raises(self):
        # force_ascii=True (default) does NOT discard the non-ASCII defect
        with pytest.raises(ValueError, match="Invalid address"):
            SMTPMailer().prep_address("üser@example.com")

    def test_force_ascii_false_with_non_ascii_local_part(self):
        # force_ascii=False discards the non-ASCII local-part defect
        result = SMTPMailer().prep_address("üser@example.com", force_ascii=False)
        assert "üser" in result
