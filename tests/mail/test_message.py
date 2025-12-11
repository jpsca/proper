import pytest

from proper.mail import EmailMessage


SUBJECT = "Subject"
CONTENT = "Content"
FROM_EMAIL = "from@example.com"


def Message(**kwargs):
    """Helper to create an EmailMessage object."""
    kwargs.setdefault("subject", SUBJECT)
    kwargs.setdefault("body", CONTENT)
    kwargs.setdefault("from_email", FROM_EMAIL)
    return EmailMessage(**kwargs)


def test_ascii():
    msg = Message(to="to@example.com")
    email = msg.message()

    assert email["Subject"] == SUBJECT
    assert email.get_payload() == CONTENT + "\n"
    assert email["From"] == FROM_EMAIL
    assert email["To"] == "to@example.com"


def test_multiple_recipients():
    msg = Message(to=["to@example.com", "other@example.com"])
    email = msg.message()

    assert email["Subject"] == SUBJECT
    assert email.get_payload() == CONTENT + "\n"
    assert email["From"] == FROM_EMAIL
    assert email["To"] == ("to@example.com, other@example.com")


def test_cc():
    msg = Message(cc="cc@example.com")
    email = msg.message()

    assert email["Cc"] == "cc@example.com"
    assert not email["To"]
    assert not email["Bcc"]
    assert msg.get_recipients() == ["cc@example.com"]


def test_multiple_cc():
    msg = Message(cc=["cc@example.com", "cc.other@example.com"])
    email = msg.message()

    print(email["Cc"])
    assert email["Cc"] == "cc@example.com, cc.other@example.com"
    assert not email["To"]
    assert not email["Bcc"]
    assert msg.get_recipients() == ["cc@example.com", "cc.other@example.com"]


def test_bcc():
    msg = Message(bcc="bcc@example.com")
    email = msg.message()

    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == ["bcc@example.com"]


def test_multiple_bcc():
    msg = Message(bcc=["bcc@example.com", "bcc.other@example.com"])
    email = msg.message()

    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == ["bcc@example.com", "bcc.other@example.com"]


def test_multiple_cc_and_to():
    msg = Message(
        to=["to@example.com", "other@example.com"],
        cc=["cc@example.com", "cc.other@example.com"],
    )
    email = msg.message()

    assert email["To"] == "to@example.com, other@example.com"
    assert email["Cc"] == "cc@example.com, cc.other@example.com"
    assert not email["Bcc"]
    assert msg.get_recipients() == [
        "to@example.com",
        "other@example.com",
        "cc@example.com",
        "cc.other@example.com",
    ]


def test_multiple_to_cc_bcc():
    msg = Message(
        to=["to@example.com", "other@example.com"],
        cc=["cc@example.com", "cc.other@example.com"],
        bcc=["bcc@example.com", "bcc.other@example.com"],
    )
    email = msg.message()

    assert email["To"] == "to@example.com, other@example.com"
    assert email["Cc"] == "cc@example.com, cc.other@example.com"
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == [
        "to@example.com",
        "other@example.com",
        "cc@example.com",
        "cc.other@example.com",
        "bcc@example.com",
        "bcc.other@example.com",
    ]


def test_reply_to():
    msg = Message(reply_to="replyto@example.com")
    email = msg.message()

    assert email["Reply-To"] == "replyto@example.com"
    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == []


def test_multiple_reply_to():
    msg = Message(reply_to=["replyto@example.com", "replyto.other@example.com"])
    email = msg.message()

    assert email["Reply-To"] == "replyto@example.com, replyto.other@example.com"
    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == []


def test_header_injection():
    msg = Message(
        subject="Subject\nInjection Test",
        to="to@example.com",
    )
    with pytest.raises(ValueError):
        msg.message()


def test_message_header_overrides():
    """Specifying dates or email-ids in the extra headers overrides the
    default values.
    """
    headers = {"date": "Fri, 09 Nov 2001 01:08:47 -0000", "Message-ID": "foo"}
    msg = Message(
        to="to@example.com",
        headers=headers,
    )
    email_str = msg.message().as_string()
    print(email_str)

    assert email_str.startswith(
        'Content-Type: text/plain; charset="utf-8"\nContent-Transfer-Encoding: 7bit\nMIME-Version: 1.0\n'
    )
    headers = [
        "Subject: Subject",
        "From: from@example.com",
        "To: to@example.com",
        "date: Fri, 09 Nov 2001 01:08:47 -0000",
        "Message-ID: foo",
    ]
    lines = set(email_str.split("\n"))
    for header in headers:
        assert header in lines

    assert email_str.endswith("\n\n" + CONTENT + "\n")


def test_from_header():
    """Make sure we can manually set the From header."""
    msg = Message(
        to="to@example.com",
        headers={"From": "from@example.com"},
    )
    email = msg.message()

    assert email["From"] == FROM_EMAIL


def test_multiple_message_call():
    """Make sure that headers are not changed when calling
    `EmailMessage.message()` again.
    """
    msg = Message(
        from_email="bounce@example.com",
        to="to@example.com",
        headers={"From": "from@example.com"},
    )
    email = msg.message()
    assert email["From"] == FROM_EMAIL
    email = msg.message()
    assert email["From"] == FROM_EMAIL


def test_html():
    html_content = "<p>This is an <strong>important</strong> email.</p>"
    msg = Message(body=html_content)
    msg.content_subtype = "html"
    email = msg.message()

    assert email.get_content_type() == "text/html"


def test_encoding():
    """Encode body correctly with other encodings than utf-8
    """
    msg = Message(
        body="Firstname Sürname is a great guy.",
        to="other@example.com",
    )
    msg.encoding = "iso-8859-1"
    email = msg.message()

    result = email.as_string().strip()
    print(result)

    assert result.startswith("""
Content-Type: text/plain; charset="iso-8859-1"
Content-Transfer-Encoding: quoted-printable
MIME-Version: 1.0
Subject: Subject
From: from@example.com
To: other@example.com
""".strip())

    # # Make sure MIME attachments also works correctly with other encodings than utf-8
    # text_content = "Firstname Sürname is a great guy."
    # html_content = "<p>Firstname Sürname is a <strong>great</strong> guy.</p>"

    # msg = EmailMessage(
    #     "Subject",
    #     text_content,
    #     "from@example.com",
    #     "to@example.com",
    #     html_content=html_content,
    # )
    # msg.encoding = "iso-8859-1"
    # email = msg.message()

    # assert email.get_payload(0).as_string() == (
    #     'Content-Type: text/plain; charset="iso-8859-1"'
    #     "\nMIME-Version: 1.0"
    #     "\nContent-Transfer-Encoding: quoted-printable"
    #     "\n\nFirstname S=FCrname is a great guy."
    # )
    # assert email.get_payload(1).as_string() == (
    #     'Content-Type: text/html; charset="iso-8859-1"'
    #     "\nMIME-Version: 1.0"
    #     "\nContent-Transfer-Encoding: quoted-printable"
    #     "\n\n<p>Firstname S=FCrname is a <strong>great</strong> guy.</p>"
    # )


# def test_attachments():
#     msg = Message()
#     msg.attach("an attachment.pdf", "%PDF-1.4.%...", mimetype="application/pdf")
#     email = msg.message()

#     assert email.is_multipart()
#     assert email.get_content_type() == "multipart/mixed"
#     assert email.get_default_type() == "text/plain"
#     assert email.get_payload(0).get_content_type() == "text/plain"
#     assert email.get_payload(1).get_content_type() == "application/pdf"


def test_dont_mangle_from_in_body():
    """Make sure that EmailMessage doesn't mangle 'From' in email body."""
    msg = Message(
        body="From the future",
        from_email="bounce@example.com",
        to="to@example.com",
        headers={"From": "from@example.com"},
    )
    email_bytes = msg.message().as_bytes()

    print(email_bytes)
    assert b">From the future" not in email_bytes
