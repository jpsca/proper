from io import StringIO

import pytest

from proper.mail import (
    BaseSender,
    EmailMessage,
    ToConsoleSender,
    ToMemorySender,
)


def make_emails():
    return [
        EmailMessage(
            from_email="from@example.com",
            subject="Subject",
            to="to@example.com",
            body=f"Content #{content}",
        ).serialize() for content in range(1, 5)]


def test_base_mailer():
    mailer = BaseSender()
    mailer.open()
    mailer.close()
    with pytest.raises(NotImplementedError):
        mailer.send_email()


def test_to_memory_mailer():
    mailer = ToMemorySender()
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_email(email1) == 1
    assert mailer.send_email(email2, email3, email4) == 3
    assert len(mailer.outbox) == 4


def test_to_console_mailer():
    stream = StringIO()
    mailer = ToConsoleSender(stream=stream)
    mailer.send_email(EmailMessage(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    ).serialize())

    value = stream.getvalue().strip()
    print(value)

    assert value.startswith("""
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: 7bit
MIME-Version: 1.0
Subject: Subject
From: from@example.com
To: to@example.com
""".strip())

    assert "\nContent\n" in value
