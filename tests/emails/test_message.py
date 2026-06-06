import pytest

from proper import App, current
from proper.emails import EmailMessage
from proper.errors import ConfigError


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
    assert msg.from_email == "no-reply@example.com"
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


def test_init_with_mailer_default_options(app):
    app.config["MAILER_DEFAULT_OPTIONS"] = {
        "from": "default@example.com",
        "subject": "Default Subject",
        "to": ["default@example.com"],
        "bcc": ["bcc@example.com"],
        "cc": ["cc@example.com"],
        "reply_to": ["reply@example.com"],
        "headers": {"X-Default": "yes"},
    }
    msg = EmailMessage()

    assert msg.from_email == "default@example.com"
    assert msg.subject == "Default Subject"
    assert msg.to == ["default@example.com"]
    assert msg.bcc == ["bcc@example.com"]
    assert msg.cc == ["cc@example.com"]
    assert msg.reply_to == ["reply@example.com"]
    assert msg.headers == {"X-Default": "yes"}


def test_init_explicit_overrides_defaults(app):
    app.config["MAILER_DEFAULT_OPTIONS"] = {
        "from": "default@example.com",
        "subject": "Default",
    }
    msg = EmailMessage(from_email="explicit@example.com", subject="Explicit")

    assert msg.from_email == "explicit@example.com"
    assert msg.subject == "Explicit"


def test_instances_dont_share_mutable_state():
    msg1 = EmailMessage(from_email="a@example.com", to="to@example.com")
    msg2 = EmailMessage(from_email="b@example.com", to="to@example.com")

    msg1.attach_alternative("html", "text/html")
    assert len(msg2.alternatives) == 0

    msg1.headers["X-Custom"] = "value"
    assert "X-Custom" not in msg2.headers


# --- _render tests ---


def _make_email_class(module_name):
    """Create an EmailMessage subclass with a controlled __module__."""
    cls = type("TestEmail", (EmailMessage,), {})
    cls.__module__ = f"app.emails.{module_name}"
    return cls


def _setup_render(app, tmp_path, templates):
    """Write template files and register the views folder with the catalog."""
    views_dir = tmp_path / "views" / "emails"
    views_dir.mkdir(parents=True)
    for name, content in templates.items():
        (views_dir / name).write_text(content)
    app.root_path = tmp_path
    app.views_path = tmp_path / "views"
    app.catalog.add_folder(app.views_path)


def test_render_html_only(app, tmp_path):
    _setup_render(app, tmp_path, {
        "welcome.jx": "{#def subject #}\n<h1>Hello {{ subject }}</h1>",
    })

    cls = _make_email_class("welcome")
    msg = cls(subject="World", to="to@example.com")
    msg._render()

    assert "<h1>Hello World</h1>" in msg.body
    assert msg.content_subtype == "html"
    assert len(msg.alternatives) == 1
    assert msg.alternatives[0]["mimetype"] == "text/plain"
    assert "Hello World" in msg.alternatives[0]["content"]


def test_render_text_only(app, tmp_path):
    _setup_render(app, tmp_path, {
        "notification.txt.jx": "{#def subject #}\nHi {{ subject }}",
    })

    cls = _make_email_class("notification")
    msg = cls(subject="there", to="to@example.com")
    msg._render()

    assert "Hi there" in msg.body
    assert msg.content_subtype == "plain"
    assert msg.alternatives == []


def test_render_html_and_text(app, tmp_path):
    _setup_render(app, tmp_path, {
        "digest.jx": "{#def subject #}\n<p>HTML {{ subject }}</p>",
        "digest.txt.jx": "{#def subject #}\nText {{ subject }}",
    })

    cls = _make_email_class("digest")
    msg = cls(subject="content", to="to@example.com")
    msg._render()

    assert "<p>HTML content</p>" in msg.body
    assert msg.content_subtype == "html"
    assert len(msg.alternatives) == 1
    assert msg.alternatives[0]["mimetype"] == "text/plain"
    assert "Text content" in msg.alternatives[0]["content"]


def test_render_no_templates(app, tmp_path):
    _setup_render(app, tmp_path, {})

    cls = _make_email_class("missing")
    msg = cls(subject="test", to="to@example.com")
    msg._render()

    assert msg.body == ""
    assert msg.content_subtype == "plain"
    assert msg.alternatives == []


# --- send() backend routing tests ---


def _multi_mailer_app():
    app = App(
        __name__,
        {
            "SECRET_KEYS": ["*" * 50],
            "DEBUG": False,
            "MAILER": "primary",
            "MAILERS": {
                "primary": {"type": "proper.emails.ToMemoryMailer"},
                "secondary": {"type": "proper.emails.ToMemoryMailer"},
            },
        },
    )
    current.app = app
    return app


def _msg():
    return EmailMessage(from_email="a@example.com", to="to@example.com", body="hi")


def test_send_uses_default_mailer():
    app = _multi_mailer_app()
    _msg().send()
    assert len(app.mailers["primary"].outbox) == 1
    assert app.mailers["secondary"].outbox == []


def test_send_via_routes_to_named_mailer():
    app = _multi_mailer_app()
    _msg().send(via="secondary")
    assert app.mailers["primary"].outbox == []
    assert len(app.mailers["secondary"].outbox) == 1


def test_send_via_default_name_matches_default():
    app = _multi_mailer_app()
    assert app.mailer is app.mailers["primary"]
    _msg().send(via="primary")
    assert len(app.mailer.outbox) == 1


def test_send_via_unknown_raises():
    _multi_mailer_app()
    with pytest.raises(ConfigError, match="Unknown mailer"):
        _msg().send(via="nope")
