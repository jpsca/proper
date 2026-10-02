import sys

import pytest

from proper.errors import ConfigError
from proper.rich_text import sanitize
from proper.rich_text.sanitizer import _get_cleaner


# --- What the editor writes is kept ---


@pytest.mark.parametrize(
    "html",
    [
        "<p>Hello <strong>world</strong>, <em>hi</em> <s>no</s> <u>yes</u></p>",
        "<h2>Title</h2><blockquote><p>Quote</p></blockquote>",
        '<ul><li>One</li></ul><ol start="3"><li value="5">Five</li></ol>',
        '<pre data-language="python">print(1 &lt; 2)</pre><p><code>x</code></p>',
        '<p><mark style="color:red;background-color:#ff0">marked</mark></p>',
        '<figure class="horizontal-divider"><hr></figure>',
        (
            '<table><thead><tr><th colspan="2">h</th></tr></thead>'
            "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
        ),
        '<p><img src="/photo.png" alt="A photo" width="10" height="20"></p>',
        "<p>line<br>break</p>",
    ],
)
def test_keeps_what_the_editor_writes(html):
    assert sanitize(html) == html


def test_keeps_the_attachment_tags():
    html = (
        '<proper-attachment sgid="12" alt="A cat" caption="Hi" presentation="gallery"'
        ' content-type="image/png" url="/x.png" filename="x.png" filesize="10"'
        ' previewable="true" width="10" height="20" content="&lt;b&gt;x&lt;/b&gt;">'
        "</proper-attachment>"
    )
    assert sanitize(html) == html


def test_attachment_tag_keeps_only_its_attributes():
    html = '<proper-attachment sgid="12" onclick="x()" data-action="y"></proper-attachment>'
    assert sanitize(html) == '<proper-attachment sgid="12"></proper-attachment>'


def test_empty():
    assert sanitize("") == ""
    assert sanitize(None) == ""
    assert sanitize(123) == ""


# --- What is removed ---


@pytest.mark.parametrize(
    "html, expected",
    [
        ("<p>Hi</p><script>alert(1)</script>", "<p>Hi</p>"),
        ("<style>p { color: red }</style><p>Hi</p>", "<p>Hi</p>"),
        ('<p onclick="x()">Hi</p>', "<p>Hi</p>"),
        ("<img src=x onerror=alert(1)>", '<img src="x">'),
        ('<iframe src="https://example.com"></iframe>', ""),
        ("<form><input name=a><button>Go</button></form>", "Go"),
        ("<svg onload=alert(1)><circle></circle></svg>", ""),
        ("<p>a<!-- comment -->b</p>", "<p>ab</p>"),
        ('<p contenteditable="true" id="x">Hi</p>', "<p>Hi</p>"),
    ],
)
def test_removes_what_is_not_allowed(html, expected):
    assert sanitize(html) == expected


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:x",
    ],
)
def test_removes_urls_with_other_schemes(url):
    assert sanitize(f'<a href="{url}">x</a>') == '<a rel="noopener noreferrer">x</a>'
    assert sanitize(f'<img src="{url}">') == "<img>"


@pytest.mark.parametrize(
    "url",
    ["https://example.com/a?b=1", "http://example.com", "mailto:a@example.com", "tel:+51", "/a/b", "#c"],
)
def test_keeps_safe_urls(url):
    assert sanitize(f'<a href="{url}">x</a>') == f'<a href="{url}" rel="noopener noreferrer">x</a>'


def test_removes_the_attributes_of_stimulus():
    """The document must not be able to run the controllers of the app."""
    html = '<div data-controller="admin" data-action="click->admin#destroy">x</div>'
    assert sanitize(html) == "<div>x</div>"


def test_keeps_only_the_allowed_css_properties():
    html = '<span style="color: red; position: fixed; background: url(javascript:x)">x</span>'
    assert sanitize(html) == '<span style="color:red">x</span>'


def test_attachment_tag_in_text_or_attribute_stays_as_text():
    """Only a real tag can be replaced with an attachment."""
    html = (
        '<p>&lt;proper-attachment sgid="1"&gt;&lt;/proper-attachment&gt;</p>'
        "<a title='<proper-attachment sgid=\"1\"></proper-attachment>'>x</a>"
    )
    out = sanitize(html)
    assert "<proper-attachment" not in out


# --- Config ---


def test_config_tags():
    config = {"RICH_TEXT_ALLOWED_TAGS": ["p"]}
    assert sanitize("<p>Hi <strong>there</strong></p>", config) == "<p>Hi there</p>"


def test_config_attributes():
    config = {"RICH_TEXT_ALLOWED_ATTRIBUTES": {"*": ["id"], "a": ["href", "target"]}}
    html = '<p id="a" class="b"><a href="/x" target="_blank" title="t">x</a></p>'
    assert sanitize(html, config) == (
        '<p id="a"><a href="/x" target="_blank" rel="noopener noreferrer">x</a></p>'
    )


def test_config_rel_attribute():
    """With `rel` allowed, the one of the document is kept and none is added."""
    config = {"RICH_TEXT_ALLOWED_ATTRIBUTES": {"a": ["href", "rel"]}}
    assert sanitize('<a href="/x" rel="nofollow">x</a>', config) == '<a href="/x" rel="nofollow">x</a>'
    assert sanitize('<a href="/x">x</a>', config) == '<a href="/x">x</a>'

    config = {"RICH_TEXT_ALLOWED_ATTRIBUTES": {"*": ["rel"], "a": ["href"]}}
    assert sanitize('<a href="/x">x</a>', config) == '<a href="/x">x</a>'


def test_config_styles():
    config = {"RICH_TEXT_ALLOWED_STYLES": ["text-align"]}
    html = '<p style="color: red; text-align: center">x</p>'
    assert sanitize(html, config) == '<p style="text-align:center">x</p>'


def test_config_url_schemes():
    config = {"RICH_TEXT_ALLOWED_URL_SCHEMES": ["https", "ftp"]}
    assert sanitize('<a href="ftp://a.b/c">x</a>', config) == (
        '<a href="ftp://a.b/c" rel="noopener noreferrer">x</a>'
    )
    assert sanitize('<a href="mailto:a@b.c">x</a>', config) == '<a rel="noopener noreferrer">x</a>'


def test_config_can_allow_a_tag_removed_with_its_content():
    config = {"RICH_TEXT_ALLOWED_TAGS": ["style", "p"]}
    assert sanitize("<style>p {}</style><p>x</p>", config) == "<style>p {}</style><p>x</p>"


def test_attachment_tags_are_kept_with_any_config():
    config = {"RICH_TEXT_ALLOWED_TAGS": ["p"], "RICH_TEXT_ALLOWED_ATTRIBUTES": {}}
    html = '<proper-attachment sgid="12" alt="x"></proper-attachment>'
    assert sanitize(html, config) == html


def test_config_of_the_app(app):
    app.config["RICH_TEXT_ALLOWED_TAGS"] = ["p"]
    assert sanitize("<p>Hi <b>there</b></p>", app.config) == "<p>Hi there</p>"


# --- nh3 ---


def test_error_when_nh3_is_not_installed(monkeypatch):
    _get_cleaner.cache_clear()
    monkeypatch.setitem(sys.modules, "nh3", None)  # makes the import fail

    with pytest.raises(ConfigError, match="RICH_TEXT_SANITIZE = False"):
        sanitize("<p>Hi</p>")

    monkeypatch.undo()
    _get_cleaner.cache_clear()
    assert sanitize("<p>Hi</p>") == "<p>Hi</p>"
