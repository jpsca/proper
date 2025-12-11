from io import StringIO

import pytest

from proper.mail import (
    BaseEmailSender,
    EmailMessage,
    ToConsoleEmailSender,
    ToMemoryEmailSender,
)


def make_emails():
    return [
        EmailMessage(
            from_email="from@example.com",
            subject="Subject",
            to="to@example.com",
            body=f"Content #{content}",
        )
        for content in range(1, 5)
    ]


def test_base_mailer():
    mailer = BaseEmailSender()
    mailer.open()
    mailer.close()
    with pytest.raises(NotImplementedError):
        mailer.send_email()


def test_to_memory_mailer():
    mailer = ToMemoryEmailSender()
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_emails(email1) == 1
    assert mailer.send_emails(email2, email3, email4) == 3
    assert len(mailer.outbox) == 4


def test_to_console_mailer():
    stream = StringIO()
    mailer = ToConsoleEmailSender(stream=stream)
    mailer.send_email(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    )

    value = stream.getvalue().strip()
    print(value)

    assert value.startswith("""
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: 7bit
MIME-Version: 1.0
Subject: Subject
From: from@example.com
To: to@example.com
Date:""".strip())

    assert "\nContent\n" in value
