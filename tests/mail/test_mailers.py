import email
from io import StringIO
from pathlib import Path

import pytest

from proper.mail import (
    BaseMailer,
    EmailMessage,
    ToConsoleMailer,
    ToFileMailer,
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

    assert mailer.send_messages(email1) == 1
    assert mailer.send_messages(email2, email3, email4) == 3
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


def test_to_file_mailer(tmp_path):
    mailer = ToFileMailer(tmp_path)

    n = mailer.send(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    )
    tmp_files = list(tmp_path.iterdir())
    assert n == 1
    assert len(tmp_files) == 1

    with tmp_files[0].open("rt") as fd:
        message = email.message_from_file(fd)

    assert message.get_content_type() == "text/plain"
    assert message.get("subject") == "Subject"
    assert message.get("from") == "from@example.com"
    assert message.get("to") == "to@example.com"


def test_to_file_mailer_dir_creation(tmp_path):
    mailer = ToFileMailer(__file__)
    assert mailer.path == Path(__file__).parent

    tmp_dir = tmp_path / "qwertyuiop12345"
    ToFileMailer(tmp_dir)

    assert tmp_dir.is_dir()


def test_to_file_mailer_unique_filename(tmp_path):
    mailer1 = ToFileMailer(tmp_path)
    mailer2 = ToFileMailer(tmp_path)
    mailer1.send(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    )
    mailer2.send(
        subject="Subject",
        body="Content",
        from_email="from@example.com",
        to="to@example.com",
    )

    assert len(list(tmp_path.iterdir())) == 2


def test_to_file_mailer_one_file(tmp_path):
    mailer = ToFileMailer(tmp_path, multifile=False)
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_messages(email1) == 1
    assert mailer.send_messages(email2, email3) == 2
    assert mailer.send_messages(email4) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_to_file_mailer_multifile(tmp_path):
    mailer = ToFileMailer(tmp_path, multifile=True)
    email1, email2, email3, email4 = make_emails()

    assert mailer.send_messages(email1) == 1
    assert mailer.send_messages(email2, email3) == 2
    assert mailer.send_messages(email4) == 1
    assert len(list(tmp_path.iterdir())) == 3
