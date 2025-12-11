from smtplib import SMTP, SMTPException

import pytest

from proper.mail import EmailMessage, SMTPEmailSender


def make_emails():
    return [
        EmailMessage(
            subject="Subject-%s" % num,
            body="Content",
            from_email="from@example.com",
            to="to@example.com",
        )
        for num in range(1, 5)
    ]


def test_sending(smtpd):
    mailer = SMTPEmailSender(host=smtpd.hostname, port=smtpd.port, use_tls=False)
    email1, email2, email3, email4 = make_emails()

    with SMTP(smtpd.hostname, smtpd.port):
        assert mailer.send_emails(email1) == 1
        assert mailer.send_emails(email2, email3) == 2
        assert mailer.send_emails(email4) == 1

    assert len(smtpd.messages) == 4

    message = smtpd.messages[0]
    print(message)
    assert message.get_content_type() == "text/plain"
    assert message.get("subject") == "Subject-1"
    assert message.get("from") == "from@example.com"
    assert message.get("to") == "to@example.com"


def test_sending_unicode(smtpd):
    mailer = SMTPEmailSender(host=smtpd.hostname, port=smtpd.port, use_tls=False)
    email = EmailMessage(
        subject="Olé",
        body="Contenido en español",
        from_email="from@example.com",
        to="to@example.com",
    )

    with SMTP(smtpd.hostname, smtpd.port):
        assert mailer.send_emails(email)

    assert len(smtpd.messages) == 1
    message = smtpd.messages[0]
    print(message)
    assert message.get_content_type() == "text/plain"
    assert message.get("subject") == "=?utf-8?q?Ol=C3=A9?="


def test_notls(smtpd):
    mailer = SMTPEmailSender(host=smtpd.hostname, port=smtpd.port, use_tls=True)
    with pytest.raises(SMTPException):
        with SMTP(smtpd.hostname, smtpd.port):
            mailer.open()
    mailer.close()


def test_fail_silently(smtpd):
    mailer = SMTPEmailSender(
        host=smtpd.hostname,
        port=smtpd.port,
        use_tls=True,
        fail_silently=True,
    )
    with SMTP(smtpd.hostname, smtpd.port):
        mailer.open()
    mailer.close()

    mailer = SMTPEmailSender(
        host="123",
        port=smtpd.port,
        use_tls=False,
        fail_silently=True,
        timeout=0.5,
    )
    with SMTP(smtpd.hostname, smtpd.port):
        mailer.open()
    mailer.close()

    mailer = SMTPEmailSender(
        host=smtpd.hostname,
        port=3000,
        use_tls=False,
        fail_silently=True,
    )
    with SMTP(smtpd.hostname, smtpd.port):
        mailer.open()
    mailer.close()
