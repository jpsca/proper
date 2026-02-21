import pytest

from proper.emails import EmailMessage


def test_basic_init():
    msg = EmailMessage(
        from_email="from@example.com",
        subject="Hello",
        body="World",
        to="to@example.com",
    )
    assert msg.from_email == "from@example.com"
    assert msg.subject == "Hello"
    assert msg.body == "World"
    assert msg.to == ["to@example.com"]
    assert msg.cc == []
    assert msg.bcc == []
    assert msg.reply_to == []
    assert msg.headers == {}
    assert msg.attachments == []
    assert msg.alternatives == []


def test_init_with_lists():
    msg = EmailMessage(
        from_email="from@example.com",
        to=["a@example.com", "b@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc1@example.com", "bcc2@example.com"],
        reply_to=["reply@example.com"],
    )
    assert msg.to == ["a@example.com", "b@example.com"]
    assert msg.cc == ["cc@example.com"]
    assert msg.bcc == ["bcc1@example.com", "bcc2@example.com"]
    assert msg.reply_to == ["reply@example.com"]


def test_init_defaults():
    msg = EmailMessage()
    assert msg.from_email == ""
    assert msg.subject == ""
    assert msg.body == ""
    assert msg.to == []
    assert msg.cc == []
    assert msg.bcc == []
    assert msg.reply_to == []
    assert msg.headers == {}


def test_init_with_headers():
    msg = EmailMessage(
        from_email="from@example.com",
        to="to@example.com",
        headers={"X-Custom": "value", "X-Priority": "1"},
    )
    assert msg.headers == {"X-Custom": "value", "X-Priority": "1"}


def test_serialize():
    msg = EmailMessage(
        from_email="from@example.com",
        subject="Subject",
        body="Body",
        to="to@example.com",
        cc="cc@example.com",
        bcc="bcc@example.com",
        reply_to="reply@example.com",
        headers={"X-Custom": "value"},
    )
    data = msg.serialize()

    assert data["charset"] == "utf-8"
    assert data["content_subtype"] == "plain"
    assert data["from_email"] == "from@example.com"
    assert data["subject"] == "Subject"
    assert data["body"] == "Body"
    assert data["to"] == ["to@example.com"]
    assert data["cc"] == ["cc@example.com"]
    assert data["bcc"] == ["bcc@example.com"]
    assert data["reply_to"] == ["reply@example.com"]
    assert data["headers"] == {"X-Custom": "value"}
    assert data["attachments"] == []
    assert data["alternatives"] == []


def test_to_dict_is_serialize():
    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    assert msg.to_dict() == msg.serialize()


def test_update():
    msg = EmailMessage(
        from_email="old@example.com",
        to="old@example.com",
        cc="old-cc@example.com",
        headers={"X-Old": "1"},
    )
    msg.update(
        from_email="new@example.com",
        to=["new@example.com"],
        cc="new-cc@example.com",
        bcc="new-bcc@example.com",
        reply_to="reply@example.com",
        headers={"X-New": "2"},
    )

    assert msg.from_email == "new@example.com"
    assert msg.to == ["new@example.com"]
    assert msg.cc == ["new-cc@example.com"]
    assert msg.bcc == ["new-bcc@example.com"]
    assert msg.reply_to == ["reply@example.com"]
    assert msg.headers == {"X-Old": "1", "X-New": "2"}


def test_update_preserves_unset_fields():
    msg = EmailMessage(
        from_email="from@example.com",
        to="to@example.com",
        cc="cc@example.com",
    )
    msg.update()

    assert msg.from_email == "from@example.com"
    assert msg.to == ["to@example.com"]
    assert msg.cc == ["cc@example.com"]


def test_attach_alternative():
    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    msg.attach_alternative("<h1>Hello</h1>", "text/html")

    assert len(msg.alternatives) == 1
    assert msg.alternatives[0] == {"content": "<h1>Hello</h1>", "mimetype": "text/html"}


def test_attach_alternative_raises_on_none_content():
    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    with pytest.raises(ValueError, match="Both content and mimetype must be provided"):
        msg.attach_alternative(None, "text/html")


def test_attach_alternative_raises_on_none_mimetype():
    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    with pytest.raises(ValueError, match="Both content and mimetype must be provided"):
        msg.attach_alternative("content", None)


def test_attach_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")

    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    msg.attach_file(str(f))

    assert len(msg.attachments) == 1
    assert msg.attachments[0]["filename"] == str(f.resolve())
    assert msg.attachments[0]["mimetype"] == "text/plain"


def test_attach_file_unknown_mimetype(tmp_path):
    f = tmp_path / "data.xyz123"
    f.write_bytes(b"\x00\x01\x02")

    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    msg.attach_file(str(f))

    assert msg.attachments[0]["mimetype"] == "application/octet-stream"


def test_attach_file_explicit_mimetype(tmp_path):
    f = tmp_path / "image.txt"
    f.write_bytes(b"\x89PNG")

    msg = EmailMessage(from_email="from@example.com", to="to@example.com")
    msg.attach_file(str(f), mimetype="image/png")

    assert msg.attachments[0]["mimetype"] == "image/png"


def test_generate_text_alternative():
    msg = EmailMessage(
        from_email="from@example.com",
        to="to@example.com",
        body="<h1>Hello</h1><p>World</p>",
    )
    msg.generate_text_alternative()

    assert len(msg.alternatives) == 1
    assert msg.alternatives[0]["mimetype"] == "text/plain"
    assert "Hello" in msg.alternatives[0]["content"]
    assert "World" in msg.alternatives[0]["content"]


def test_multiple_attachments_and_alternatives(tmp_path):
    f1 = tmp_path / "a.txt"
    f1.write_text("aaa")
    f2 = tmp_path / "b.txt"
    f2.write_text("bbb")

    msg = EmailMessage(from_email="from@example.com", to="to@example.com", body="body")
    msg.attach_file(str(f1))
    msg.attach_file(str(f2))
    msg.attach_alternative("<b>body</b>", "text/html")

    data = msg.serialize()
    assert len(data["attachments"]) == 2
    assert len(data["alternatives"]) == 1


def test_instances_dont_share_mutable_state():
    msg1 = EmailMessage(from_email="a@example.com", to="to@example.com")
    msg2 = EmailMessage(from_email="b@example.com", to="to@example.com")

    msg1.attach_alternative("html", "text/html")
    assert len(msg2.alternatives) == 0

    msg1.headers["X-Custom"] = "value"
    assert "X-Custom" not in msg2.headers
