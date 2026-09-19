"""Embedded attachments are stored without the attributes derived from the
attachment row (`DERIVED_ATTRS`), and get them back, fresh, for the editor.

The point: the embed URL is signed with the environment's secret keys, so a
stored copy breaks when the database moves or the keys change.
"""
from io import BytesIO
from types import SimpleNamespace

import pytest

from proper import App, Controller, current
from proper.forms import RichTextField as RichTextFormField
from proper.rich_text.document import (
    DERIVED_ATTRS,
    RichTextDocument,
    dehydrate_attachments,
    hydrate_attachments,
)
from proper.router import Route


class StorageRedirectController(Controller):
    """Gives `attachment.url` a route to point at (named `StorageRedirect.show`)."""

    def show(self):
        pass


@pytest.fixture(autouse=True)
def storage_route(app):
    app.router.add_route(
        Route(
            method="GET",
            path="storage/redirect/:token/:filename",
            to=StorageRedirectController.show,
        )
    )


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf


def _editor_tag(att, *, url=None, extra=' alt="A cat" caption="Look: a &amp; b" presentation="gallery"'):
    """The tag as the editor writes it for a fresh upload."""
    url = url or att.url
    return (
        f'<proper-attachment sgid="{att.id}" previewable="true" url="{url}"{extra} '
        f'content-type="{att.content_type}" filename="{att.filename}" '
        f'filesize="{att.byte_size}"></proper-attachment>'
    )


# --- dehydrate_attachments


def test_dehydrate_drops_only_the_derived_attributes():
    html = (
        '<p>Hi</p><proper-attachment sgid="abc" previewable="true" '
        'url="/storage/redirect/tok/cat.png" alt="A cat" caption="Look: a &amp; b" '
        'content-type="image/png" filename="cat.png" filesize="123" '
        'presentation="gallery" width="640" data-url="keep-me"></proper-attachment><p>Bye</p>'
    )
    out = dehydrate_attachments(html)
    assert out == (
        '<p>Hi</p><proper-attachment sgid="abc" alt="A cat" caption="Look: a &amp; b" '
        'presentation="gallery" width="640" data-url="keep-me"></proper-attachment><p>Bye</p>'
    )
    for name in DERIVED_ATTRS:
        assert f' {name}="' not in out


def test_dehydrate_leaves_other_html_alone():
    html = '<p>See <a href="/x" url="not-an-embed">this</a></p><img src="/a.png" filename="a.png">'
    assert dehydrate_attachments(html) == html


def test_dehydrate_is_case_insensitive_and_idempotent():
    html = '<PROPER-ATTACHMENT sgid="abc" URL="/x" Filename="a.png"></PROPER-ATTACHMENT>'
    once = dehydrate_attachments(html)
    assert "URL=" not in once and "Filename=" not in once
    assert 'sgid="abc"' in once
    assert dehydrate_attachments(once) == once


@pytest.mark.parametrize("value", ["", None])
def test_dehydrate_passes_empty_values_through(value):
    assert dehydrate_attachments(value) == value


# --- hydrate_attachments


def test_hydrate_rebuilds_the_attributes_from_the_rows(Attachment):
    att = Attachment(_make_file(b"x" * 10, "cat.png", "image/png"))
    att.save()
    stored = f'<p>Hi</p><proper-attachment sgid="{att.id}" alt="A cat"></proper-attachment>'

    out = hydrate_attachments(stored, {str(att.id): att})

    assert out.startswith(f'<p>Hi</p><proper-attachment sgid="{att.id}" alt="A cat" url="/storage/redirect/')
    assert 'filename="cat.png"' in out
    assert 'content-type="image/png"' in out
    assert 'filesize="10"' in out
    assert 'previewable="true"' in out


def test_hydrate_replaces_stale_values(Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    stale = _editor_tag(att, url="/storage/redirect/signed-somewhere-else/cat.png")

    out = hydrate_attachments(stale, {str(att.id): att})

    assert "signed-somewhere-else" not in out
    assert out.count(' url="') == 1
    assert out.count(' filename="') == 1
    # What the author typed is untouched, byte for byte.
    assert ' alt="A cat" caption="Look: a &amp; b" presentation="gallery"' in out


def test_hydrate_does_not_mark_non_previewable_files(Attachment):
    att = Attachment(_make_file(b"x", "notes.txt", "text/plain"))
    att.save()
    out = hydrate_attachments(f'<proper-attachment sgid="{att.id}"></proper-attachment>', {str(att.id): att})
    assert "previewable" not in out
    assert 'filename="notes.txt"' in out


def test_hydrate_leaves_unknown_attachments_dehydrated():
    html = '<proper-attachment sgid="gone" url="/old" alt="x"></proper-attachment>'
    assert hydrate_attachments(html, {}) == '<proper-attachment sgid="gone" alt="x"></proper-attachment>'


def test_hydrate_escapes_the_values():
    row = SimpleNamespace(
        url='/u?a=1&b="2"', filename="a<b>.png", content_type="image/png",
        byte_size=1, is_previewable=False,
    )
    out = hydrate_attachments('<proper-attachment sgid="x"></proper-attachment>', {"x": row})
    assert 'url="/u?a=1&amp;b=&#34;2&#34;"' in out
    assert 'filename="a&lt;b&gt;.png"' in out


@pytest.mark.parametrize("value", ["", None])
def test_hydrate_passes_empty_values_through(value):
    assert hydrate_attachments(value, {}) == value


# --- Model field: nothing derived reaches the database


def _stored_body(Post, post):
    cursor = Post._meta.database.execute_sql("SELECT body FROM post WHERE id = ?", (post.id,))
    return cursor.fetchone()[0]


def test_the_field_stores_documents_dehydrated(Post, Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()

    post = Post.create(body=f"<p>Hi</p>{_editor_tag(att)}")

    stored = _stored_body(Post, post)
    assert "/storage/redirect/" not in stored
    for name in DERIVED_ATTRS:
        assert f' {name}="' not in stored
    assert f'sgid="{att.id}"' in stored
    assert 'alt="A cat"' in stored


def test_the_field_also_dehydrates_document_values(Post, Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    post = Post.create(body=RichTextDocument(_editor_tag(att), Attachment))
    assert "/storage/redirect/" not in _stored_body(Post, post)


def test_a_stored_document_still_renders_and_lists_its_attachments(Post, Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    post = Post.get_by_id(Post.create(body=_editor_tag(att)).id)
    assert [a.id for a in post.body.attachments] == [att.id]


# --- The editor gets fresh, valid URLs


def test_to_editor_html_gives_urls_valid_in_this_environment(Post, Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    post = Post.get_by_id(Post.create(body=f"<p>Hi</p>{_editor_tag(att)}").id)

    html = post.body.to_editor_html()

    token = html.split('url="/storage/redirect/')[1].split("/")[0]
    assert Attachment.get_signed(token, salt="redirect", max_age=None).id == att.id
    assert html.startswith("<p>Hi</p><proper-attachment ")
    assert 'caption="Look: a &amp; b"' in html


def test_documents_signed_in_another_environment_are_repaired(app, Post, Attachment, db):
    """A database copied from an environment with different secret keys has
    URLs this one rejects. Nothing to migrate: the editor never sees them.
    """
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    post = Post.create(body="<p>placeholder</p>")

    other = App(__name__, {"SECRET_KEYS": ["another-environment-" * 3]})
    foreign_token = other.dumps({"id": str(att.id), "fp": None}, salt="redirect")
    current.app = app  # creating `other` made it the current app
    assert Attachment.get_signed(foreign_token, salt="redirect", max_age=None) is None

    # Written straight to the table, as a copied database would have it.
    legacy = _editor_tag(att, url=f"/storage/redirect/{foreign_token}/cat.png")
    db.execute_sql("UPDATE post SET body = ? WHERE id = ?", (legacy, post.id))

    html = Post.get_by_id(post.id).body.to_editor_html()

    assert foreign_token not in html
    token = html.split('url="/storage/redirect/')[1].split("/")[0]
    assert Attachment.get_signed(token, salt="redirect", max_age=None).id == att.id


def test_to_editor_html_without_attachment_cls():
    doc = RichTextDocument('<p>x</p><proper-attachment sgid="a" url="/old"></proper-attachment>')
    assert doc.to_editor_html() == '<p>x</p><proper-attachment sgid="a"></proper-attachment>'


# --- Form field


def test_the_form_field_hands_the_editor_hydrated_html(Post, Attachment):
    att = Attachment(_make_file(b"x", "cat.png", "image/png"))
    att.save()
    post = Post.get_by_id(Post.create(body=_editor_tag(att)).id)

    value = RichTextFormField().filter_value(post.body)

    assert 'url="/storage/redirect/' in value
    assert 'filename="cat.png"' in value


def test_the_form_field_passes_submitted_strings_through():
    submitted = '<p>Hi</p><proper-attachment sgid="a" url="/x"></proper-attachment>'
    assert RichTextFormField().filter_value(submitted) == submitted
