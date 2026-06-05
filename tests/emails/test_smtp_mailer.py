import smtplib
from smtplib import SMTPException

import pytest

from proper.emails import EmailMessage, SMTPMailer


def make_emails():
    return [
        EmailMessage(
            subject="Subject-%s" % num,
            body="Content",
            from_email="from@example.com",
            to="to@example.com",
        ).serialize()
        for num in range(1, 5)
    ]


def test_tls_ssl_mutual_exclusivity():
    with pytest.raises(ValueError, match="mutually exclusive"):
        SMTPMailer(use_tls=True, use_ssl=True)


def test_send_empty_messages(smtpd):
    mailer = SMTPMailer(host=smtpd.hostname, port=smtpd.port, use_tls=False)
    assert mailer.send_now() == 0


def test_prep_address():
    mailer = SMTPMailer()
    assert mailer.prep_address("user@example.com") == "user@example.com"


def test_prep_address_unicode_domain():
    mailer = SMTPMailer()
    result = mailer.prep_address("user@münchen.de")
    assert result == "user@xn--mnchen-3ya.de"


def test_prep_address_invalid():
    mailer = SMTPMailer()
    with pytest.raises(ValueError, match="Invalid address"):
        mailer.prep_address("not an email, another")


def test_connection_class():
    mailer_plain = SMTPMailer(use_tls=False, use_ssl=False)
    assert mailer_plain.connection_class is smtplib.SMTP

    mailer_ssl = SMTPMailer(use_ssl=True)
    assert mailer_ssl.connection_class is smtplib.SMTP_SSL


def test_sending(smtpd):
    mailer = SMTPMailer(host=smtpd.hostname, port=smtpd.port, use_tls=False)
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_now(email1) == 1
    assert mailer.send_now(email2, email3) == 2
    assert mailer.send_now(email4) == 1

    assert len(smtpd.messages) == 4

    message = smtpd.messages[0]
    print(message)
    assert message.get_content_type() == "text/plain"
    assert message.get("subject") == "Subject-1"
    assert message.get("from") == "from@example.com"
    assert message.get("to") == "to@example.com"


def test_sending_unicode(smtpd):
    mailer = SMTPMailer(host=smtpd.hostname, port=smtpd.port, use_tls=False)
    email = EmailMessage(
        subject="Olé",
        body="Contenido en español",
        from_email="from@example.com",
        to="to@example.com",
    ).serialize()

    assert mailer.send_now(email)

    assert len(smtpd.messages) == 1
    message = smtpd.messages[0]
    print(message)
    assert message.get_content_type() == "text/plain"
    assert message.get("subject") == "=?utf-8?q?Ol=C3=A9?="


def test_notls(smtpd):
    mailer = SMTPMailer(host=smtpd.hostname, port=smtpd.port, use_tls=True)
    with pytest.raises(SMTPException):
        mailer.open()
    mailer.close()


def test_fail_silently(smtpd):
    mailer = SMTPMailer(
        host=smtpd.hostname,
        port=smtpd.port,
        use_tls=True,
        fail_silently=True,
        timeout=0.1,
    )
    mailer.open()
    mailer.close()

    mailer = SMTPMailer(
        host="123",
        port=smtpd.port,
        use_tls=False,
        fail_silently=True,
        timeout=0.5,
    )
    mailer.open()
    mailer.close()

    mailer = SMTPMailer(
        host=smtpd.hostname,
        port=3000,
        use_tls=False,
        fail_silently=True,
        timeout=0.1,
    )
    mailer.open()
    mailer.close()
