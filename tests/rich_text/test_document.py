from io import BytesIO
from pathlib import Path

import pytest
from markupsafe import Markup

import proper
from proper import Controller
from proper.rich_text import RichTextDocument
from proper.router import Route


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf


def _attachment_tag(att_id: str, **attrs) -> str:
    attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    spacer = " " + attr_str if attr_str else ""
    return f'<proper-attachment sgid="{att_id}"{spacer}></proper-attachment>'


# --- Basics ---


def test_to_html_returns_stored_html():
    html = "<p>Hello</p>"
    doc = RichTextDocument(html)
    assert doc.to_html() == html


def test_str_returns_plain_text():
    doc = RichTextDocument("<p>Hola</p>")
    assert str(doc) == "Hola"


def test_repr_includes_html():
    doc = RichTextDocument("<p>x</p>")
    assert "RichTextDocument" in repr(doc)
    assert "<p>x</p>" in repr(doc)


def test_equality_with_other_document():
    a = RichTextDocument("<p>x</p>")
    b = RichTextDocument("<p>x</p>")
    assert a == b


def test_equality_with_string():
    doc = RichTextDocument("<p>x</p>")
    assert doc == "<p>x</p>"


def test_inequality_with_unrelated():
    doc = RichTextDocument("<p>x</p>")
    assert (doc == 42) is False


def test_none_html_becomes_empty():
    doc = RichTextDocument(None)  # type: ignore
    assert doc.to_html() == ""


# --- Attachments property ---


def test_attachments_empty_when_no_embeds(Attachment):
    doc = RichTextDocument("<p>nothing</p>", attachment_cls=Attachment)
    assert doc.attachments == []


def test_attachments_empty_when_no_attachment_cls():
    doc = RichTextDocument(_attachment_tag("x"))
    assert doc.attachments == []


def test_attachments_resolved_from_db(Attachment):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        _attachment_tag(str(att.id)),
        attachment_cls=Attachment,
    )
    resolved = doc.attachments
    assert len(resolved) == 1
    assert resolved[0].id == att.id


def test_attachments_in_document_order(Attachment):
    a = Attachment(_make_file(b"a", "a.txt"))
    a.save()
    b = Attachment(_make_file(b"b", "b.txt"))
    b.save()

    html = (
        _attachment_tag(str(b.id))
        + "<p></p>"
        + _attachment_tag(str(a.id))
    )
    doc = RichTextDocument(html, attachment_cls=Attachment)
    ordered = [str(att.id) for att in doc.attachments]
    assert ordered == [str(b.id), str(a.id)]


def test_attachments_dedupes_repeated_ids(Attachment):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    html = _attachment_tag(str(att.id)) + _attachment_tag(str(att.id))
    doc = RichTextDocument(html, attachment_cls=Attachment)
    assert len(doc.attachments) == 1


def test_attachments_skips_missing_rows(Attachment):
    """An attachment ID in the HTML that no longer exists in the DB is
    silently skipped - old documents referencing purged blobs still
    render (without the embed) instead of crashing.
    """
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    html = (
        _attachment_tag(str(att.id))
        + _attachment_tag("00000000-0000-0000-0000-000000000000")
    )
    doc = RichTextDocument(html, attachment_cls=Attachment)
    assert len(doc.attachments) == 1


def test_attachments_cached_across_calls(Attachment):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        _attachment_tag(str(att.id)),
        attachment_cls=Attachment,
    )
    first = doc.attachments
    second = doc.attachments
    assert len(first) == 1
    assert len(second) == 1


def test_attachments_handles_non_string_html(Attachment):
    """Defensive: a non-string html input shouldn't crash."""
    doc = RichTextDocument(None, attachment_cls=Attachment)  # type: ignore
    assert doc.attachments == []


def test_non_string_html_renders_empty(Attachment):
    doc = RichTextDocument(123, attachment_cls=Attachment)  # type: ignore
    assert doc.attachments == []
    assert str(doc.__html__()) == ""


# --- __html__ ---


def test_html_structural_content_only():
    """No embeds → no catalog dependency needed."""
    doc = RichTextDocument("<p>Hi</p>")
    assert str(doc.__html__()) == "<p>Hi</p>"


def test_html_returns_markup_safe_string():
    """The result must carry the Markup type so Jinja renders it raw."""
    doc = RichTextDocument("")
    assert isinstance(doc.__html__(), Markup)


def test_html_embed_without_attachment_cls_collapses():
    """An attachment tag with no attachment_cls renders as empty (the
    document doesn't know how to look it up)."""
    html = (
        "<p>before</p>"
        + _attachment_tag("x")
        + "<p>after</p>"
    )
    doc = RichTextDocument(html)
    out = str(doc.__html__())
    assert "<p>before</p>" in out
    assert "<p>after</p>" in out
    assert "proper-attachment" not in out


# --- __html__ is sanitized ---


ATTACHMENT_VIEW = (
    Path(proper.__file__).parent
    / "_blueprints"
    / "addon_rich_text"
    / "[[app_name]]"
    / "views"
    / "rich_text_attachment.jx"
)


class StorageRedirectController(Controller):
    """Gives `attachment.url` a route to point at (named `StorageRedirect.show`)."""

    def show(self):
        pass


@pytest.fixture()
def attachment_view(app, tmp_path):
    """The app renders the attachments with the component of the addon."""
    views = tmp_path / "views"
    views.mkdir()
    (views / "rich_text_attachment.jx").write_text(ATTACHMENT_VIEW.read_text())
    app.catalog.add_folder(views)
    app.router.add_route(
        Route(
            method="GET",
            path="storage/redirect/:token/:filename",
            to=StorageRedirectController.show,
        )
    )


def test_html_is_sanitized(app):
    doc = RichTextDocument(
        '<p onclick="x()">Hi <a href="javascript:x">there</a></p><script>alert(1)</script>'
    )
    assert str(doc.__html__()) == '<p>Hi <a rel="noopener noreferrer">there</a></p>'


def test_html_is_sanitized_without_an_app():
    from proper import current

    current.app = None
    doc = RichTextDocument("<p>Hi</p><script>alert(1)</script>")
    assert str(doc.__html__()) == "<p>Hi</p>"


def test_stored_html_is_not_changed(app):
    html = "<p>Hi</p><script>alert(1)</script>"
    doc = RichTextDocument(html)
    doc.__html__()
    assert doc.to_html() == html


def test_html_uses_the_config_of_the_app(app):
    app.config["RICH_TEXT_ALLOWED_TAGS"] = ["p"]
    doc = RichTextDocument("<p>Hi <strong>there</strong></p>")
    assert str(doc.__html__()) == "<p>Hi there</p>"


def test_html_is_not_sanitized_if_the_config_says_so(app):
    app.config["RICH_TEXT_SANITIZE"] = False
    html = '<p onclick="x()">Hi</p><script>alert(1)</script>'
    doc = RichTextDocument(html)
    assert str(doc.__html__()) == html
    assert doc.to_safe_html() == html


def test_to_safe_html_keeps_the_attachment_tags(app):
    html = "<p>Hi</p>" + _attachment_tag("1", alt="x") + "<script>alert(1)</script>"
    doc = RichTextDocument(html)
    assert doc.to_safe_html() == "<p>Hi</p>" + _attachment_tag("1", alt="x")


def test_html_renders_the_attachments_after_sanitizing(Attachment, attachment_view):
    """The output of the attachment component is trusted: it is not sanitized."""
    att = Attachment(_make_file(b"x", "report.pdf", "application/pdf"))
    att.save()
    html = (
        '<p onclick="x()">before</p>'
        + _attachment_tag(str(att.id), onclick="x()")
        + "<script>alert(1)</script>"
    )
    doc = RichTextDocument(html, attachment_cls=Attachment)

    out = str(doc.__html__())

    assert out.startswith("<p>before</p>")
    assert "onclick" not in out
    assert "<script" not in out
    # `target` and `data-content-type` are not in the allowlist of the documents
    assert f'<a href="{att.url}" target="_blank" rel="noopener">' in out
    assert 'data-content-type="application/pdf"' in out
    assert '<strong class="attachment__name">report.pdf</strong>' in out


def test_html_attachment_attributes_are_escaped_once(app, tmp_path, Attachment):
    views = tmp_path / "views"
    views.mkdir()
    (views / "rich_text_attachment.jx").write_text(
        '{#def attachment, alt: str = "", caption: str = "" #}'
        '<img alt="{{ alt }}"><figcaption>{{ caption }}</figcaption>'
    )
    app.catalog.add_folder(views)
    att = Attachment(_make_file(b"x", "photo.png", "image/png"))
    att.save()
    doc = RichTextDocument(
        _attachment_tag(
            str(att.id),
            alt="Tom &amp; &quot;Jerry&quot;",
            caption="1 &lt; 2 &lt;script&gt;",
        ),
        attachment_cls=Attachment,
    )

    assert str(doc.__html__()) == (
        '<img alt="Tom &amp; &#34;Jerry&#34;">'
        "<figcaption>1 &lt; 2 &lt;script&gt;</figcaption>"
    )
