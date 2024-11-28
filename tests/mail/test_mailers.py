from io import StringIO

import pytest

from proper.mail import (
    BaseMailer,
    EmailMessage,
    ToConsoleMailer,
    ToMemoryMailer,
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
    mailer = BaseMailer()
    mailer.open()
    mailer.close()
    with pytest.raises(NotImplementedError):
        mailer.send()


def test_to_memory_mailer():
    mailer = ToMemoryMailer()
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_emails(email1) == 1
    assert mailer.send_emails(email2, email3, email4) == 3
    assert len(mailer.outbox) == 4
    assert mailer.outbox[1] == email2


def test_to_console_mailer():
    stream = StringIO()
    mailer = ToConsoleMailer(stream=stream)
    mailer.send(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    )

    value = stream.getvalue()
    assert value.startswith(
        'Content-Type: text/plain; charset="utf-8"'
        "\nMIME-Version: 1.0"
        "\nContent-Transfer-Encoding: base64"
        "\nSubject: Subject"
        "\nFrom: from@example.com"
        "\nTo: to@example.com"
        "\nDate: "
    )
