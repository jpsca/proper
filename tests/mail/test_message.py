import re

import pytest

from proper.mail import EmailMessage


def Message(**kwargs):
    """Helper to create an EmailMessage object."""
    kwargs.setdefault("subject", "Subject")
    kwargs.setdefault("body", "Content")
    kwargs.setdefault("from_email", "from@example.com")
    return EmailMessage(**kwargs)


def test_ascii():
    msg = Message(to="to@example.com")
    email = msg.render()

    assert email["Subject"] == "Subject"
    assert email.get_payload() == "Content"
    assert email["From"] == "from@example.com"
    assert email["To"] == "to@example.com"


def test_multiple_recipients():
    msg = Message(to=["to@example.com", "other@example.com"])
    email = msg.render()

    assert email["Subject"] == "Subject"
    assert email.get_payload() == "Content"
    assert email["From"] == "from@example.com"
    assert email["To"] == ("to@example.com, other@example.com")


def test_cc():
    msg = Message(cc="cc@example.com")
    email = msg.render()

    assert email["Cc"] == "cc@example.com"
    assert not email["To"]
    assert not email["Bcc"]
    assert msg.get_recipients() == ["cc@example.com"]


def test_multiple_cc():
    msg = Message(cc=["cc@example.com", "cc.other@example.com"])
    email = msg.render()

    print(email["Cc"])
    assert email["Cc"] == "cc@example.com, cc.other@example.com"
    assert not email["To"]
    assert not email["Bcc"]
    assert msg.get_recipients() == ["cc@example.com", "cc.other@example.com"]


def test_bcc():
    msg = Message(bcc="bcc@example.com")
    email = msg.render()

    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == ["bcc@example.com"]


def test_multiple_bcc():
    msg = Message(bcc=["bcc@example.com", "bcc.other@example.com"])
    email = msg.render()

    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == ["bcc@example.com", "bcc.other@example.com"]


def test_multiple_cc_and_to():
    msg = Message(
        to=["to@example.com", "other@example.com"],
        cc=["cc@example.com", "cc.other@example.com"],
    )
    email = msg.render()

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
    email = msg.render()

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
    email = msg.render()

    assert email["Reply-To"] == "replyto@example.com"
    assert not email["To"]
    assert not email["Cc"]
    assert not email["Bcc"]  # as it should
    assert msg.get_recipients() == []


def test_multiple_reply_to():
    msg = Message(reply_to=["replyto@example.com", "replyto.other@example.com"])
    email = msg.render()

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
        msg.render()


def test_message_header_overrides():
    """Specifying dates or email-ids in the extra headers overrides the
    default values.
    """
    headers = {"date": "Fri, 09 Nov 2001 01:08:47 -0000", "Message-ID": "foo"}
    msg = Message(
        to="to@example.com",
        headers=headers,
    )
    email_str = msg.render().as_string()

    assert email_str.startswith(
        'Content-Type: text/plain; charset="utf-8"\nMIME-Version: 1.0\n'
    )
    headers = [
        "Content-Transfer-Encoding: 7bit",
        "Subject: Subject",
        "From: from@example.com",
        "To: to@example.com",
        "date: Fri, 09 Nov 2001 01:08:47 -0000",
        "Message-ID: foo",
    ]
    lines = set(email_str.split("\n"))
    for header in headers:
        assert header in lines
    assert email_str.endswith("\n\nContent")


def test_from_header():
    """Make sure we can manually set the From header."""
    msg = Message(
        to="to@example.com",
        headers={"From": "from@example.com"},
    )
    email = msg.render()

    assert email["From"] == "from@example.com"


def test_multiple_message_call():
    """Make sure that headers are not changed when calling
    `EmailMessage.render()` again.
    """
    msg = Message(
        from_email="bounce@example.com",
        to="to@example.com",
        headers={"From": "from@example.com"},
    )
    email = msg.render()
    assert email["From"] == "from@example.com"
    email = msg.render()
    assert email["From"] == "from@example.com"


def test_unicode_address_header():
    """When a to/from/cc header contains unicode,
    make sure the msg addresses are parsed correctly (especially with
    regards to commas).
    """
    msg = Message(
        to=['"Firstname Sürname" <to@example.com>', "other@example.com"],
    )
    email = msg.render()
    assert (
        email["To"]
        == "=?utf-8?q?Firstname_S=C3=BCrname?= <to@example.com>, other@example.com"
    )

    msg = Message(
        to=["other@example.com", '"Sürname, Firstname" <to@example.com>'],
    )
    email = msg.render()
    assert (
        email["To"]
        == "other@example.com, =?utf-8?q?S=C3=BCrname=2C_Firstname?= <to@example.com>"
    )

    msg = Message(
        to=["other@example.com", "à" * 50 + " <to@example.com>"],
    )
    email = msg.render()
    assert email["To"] == (
        "other@example.com, "
        + "=?utf-8?b?"
        + "w6DDoMOg" * 16
        + "w6DDoA==?= <to@example.com>"
    )


def test_unicode_headers():
    headers = {
        "Sender": '"Firstname Sürname" <sender@example.com>',
        "Comments": "My Sürname is non-ASCII",
    }
    msg = Message(
        subject="Gżegżółka",
        to="to@example.com",
        headers=headers,
    )
    email = msg.render()

    assert email["Subject"] == "=?utf-8?b?R8W8ZWfFvMOzxYJrYQ==?="
    assert email["Sender"] == "=?utf-8?q?Firstname_S=C3=BCrname?= <sender@example.com>"
    assert email["Comments"] == "=?utf-8?q?My_S=C3=BCrname_is_non-ASCII?="


def test_html():
    html_content = "<p>This is an <strong>important</strong> email.</p>"
    msg = Message(body=html_content, html=True)
    email = msg.render()

    assert email.get_content_type() == "text/html"


# def test_alternative():
#     text_content = "This is an important email."
#     html_content = "<p>This is an <strong>important</strong> email.</p>"

#     msg = Message(subject, text_content, from_email, to, html_content=html_content)
#     email = msg.render()

#     assert email.is_multipart()
#     assert email.get_content_type() == "multipart/alternative"
#     assert email.get_default_type() == "text/plain"
#     assert email.get_payload(0).get_content_type() == "text/plain"
#     assert email.get_payload(1).get_content_type() == "text/html"


def test_encoding():
    """Encode body correctly with other encodingsthan utf-8
    """
    msg = Message(
        body="Firstname Sürname is a great guy.",
        to="other@example.com",
    )
    msg.encoding = "iso-8859-1"
    email = msg.render()

    assert email.as_string().startswith(
        'Content-Type: text/plain; charset="iso-8859-1"'
        "\nMIME-Version: 1.0"
        "\nContent-Transfer-Encoding: quoted-printable"
        "\nSubject: Subject"
        "\nFrom: from@example.com"
        "\nTo: other@example.com"
    )
    assert email.get_payload() == "Firstname S=FCrname is a great guy."

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
    # email = msg.render()

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
#     email = msg.render()

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
    email_bytes = msg.render().as_bytes()

    print(email_bytes)
    assert b">From the future" not in email_bytes



def test_7bit_no_quoted_printable():
    """Shouldn't use quoted printable, should detect it can represent content
    with 7 bit data.
    """
    msg = Message(body="Body with only ASCII characters.")
    email_str = msg.render().as_string()

    assert "Content-Transfer-Encoding: quoted-printable" not in email_str
    assert "Content-Transfer-Encoding: 7bit" in email_str


def test_8bit_no_quoted_printable():
    """Shouldn't use quoted printable, should detect it can represent content
    with 8 bit data.
    """
    msg = Message(body="Body with latin characters: àáä.")
    email_str = msg.render().as_string()

    assert "Content-Transfer-Encoding: quoted-printable" not in email_str
    assert "Content-Transfer-Encoding: 8bit" in email_str

    msg = Message(body="Body with non latin characters: А Б В Г Д Е Ж Ѕ З И І К Л М Н О П.")
    email_str = msg.render().as_string()

    assert "Content-Transfer-Encoding: quoted-printable" not in email_str
    assert "Content-Transfer-Encoding: 8bit" in email_str


def test_invalid_destination():
    dest = "toБ@example.com"
    msg = Message(to=dest)
    email = msg.render()

    assert email["To"] != dest


rx_message_id = re.compile(
    r"^<[0-9]{14}\.[0-9]+\.[0-9a-f]+\.[0-9]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*>$",
    re.IGNORECASE,
)


def test_message_id():
    email1 = Message(subject="Subject 1", to="to@example.com")
    msg1 = email1.render()
    mid1 = msg1["Message-ID"]
    print("Message-ID 1:", mid1)
    assert rx_message_id.match(mid1)

    email2 = Message(subject="Subject 2", to="to@example.com")
    msg2 = email2.render()
    mid2 = msg2["Message-ID"]
    print("Message-ID 2:", mid2)
    assert rx_message_id.match(mid2)
    assert mid2 != mid1
