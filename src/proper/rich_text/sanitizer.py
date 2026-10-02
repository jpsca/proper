"""Sanitizer of the HTML of rich text documents.

The HTML of a document comes from a form, so it can be anything, no matter
what the editor does in the browser. `RichTextDocument.__html__` passes it
through `sanitize()` before rendering it: only the tags, attributes, CSS
properties and URL schemes of an allowlist are kept.

The allowlist is read from the config of the app. The addon installs a
`config/rich_text.py` file with these settings:

- `RICH_TEXT_SANITIZE`: `False` renders the documents as they are stored.
  Only for apps where every author of rich text is trusted.
- `RICH_TEXT_ALLOWED_TAGS`: list of tag names.
- `RICH_TEXT_ALLOWED_ATTRIBUTES`: dict of tag name -> list of attributes.
  The ones under `"*"` are allowed in every tag.
- `RICH_TEXT_ALLOWED_STYLES`: list of the CSS properties kept in a `style`
  attribute (when `style` is an allowed attribute).
- `RICH_TEXT_ALLOWED_URL_SCHEMES`: list of the URL schemes allowed in
  attributes like `href` or `src`. Relative URLs are always allowed.

A missing setting takes the default of this module.

The `<proper-attachment>` tags are always kept: they are placeholders
that the document replaces, after sanitizing, with the output of the
`rich_text_attachment.jx` component.

The work is done by [nh3](https://nh3.readthedocs.io/), which the addon adds
to the dependencies of the app.
"""
import typing as t
from functools import lru_cache

from ..errors import ConfigError


if t.TYPE_CHECKING:
    import nh3


ATTACHMENT_TAG = "proper-attachment"

# The attributes that the editor writes in an attachment tag.
ATTACHMENT_ATTRIBUTES = (
    "alt",
    "caption",
    "content",
    "content-type",
    "filename",
    "filesize",
    "height",
    "presentation",
    "previewable",
    "sgid",
    "url",
    "width",
)

ALLOWED_TAGS = (
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "col",
    "colgroup",
    "del",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "ins",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
)

ALLOWED_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "*": ("class", "style", "title"),
    "a": ("href",),
    "img": ("src", "alt", "width", "height"),
    "li": ("value",),
    "ol": ("start",),
    "pre": ("data-language", "data-highlight-language"),
    "td": ("colspan", "rowspan"),
    "th": ("colspan", "rowspan"),
}

ALLOWED_STYLES = ("color", "background-color")

ALLOWED_URL_SCHEMES = ("http", "https", "mailto", "tel")

# Tags removed with everything inside them, instead of leaving their text.
CLEAN_CONTENT_TAGS = frozenset({"script", "style"})

LINK_REL = "noopener noreferrer"

MISSING_NH3_MESSAGE = """The rich text documents are sanitized with `nh3`, and it is not installed.

Add it to the dependencies of your project (e.g.: `uv add nh3`).

If every author of rich text in your app is trusted, you can instead set
`RICH_TEXT_SANITIZE = False` in your config to render the documents as
they are stored.
"""


def sanitize(html: str, config: t.Mapping[str, t.Any] | None = None) -> str:
    """Return `html` with only the tags, attributes, CSS properties and URL
    schemes allowed by `config`.

    Arguments:
        html:
            The HTML of a rich text document.
        config:
            The config of the app, or any mapping with the
            `RICH_TEXT_ALLOWED_*` settings. The missing ones take
            the defaults of this module.

    Raises:
        `ConfigError` if `nh3` isn't installed.

    """
    if not isinstance(html, str) or not html:
        return ""
    config = config or {}
    attributes = config.get("RICH_TEXT_ALLOWED_ATTRIBUTES", ALLOWED_ATTRIBUTES)
    cleaner = _get_cleaner(
        tags=frozenset(config.get("RICH_TEXT_ALLOWED_TAGS", ALLOWED_TAGS)),
        attributes=frozenset(
            (tag, frozenset(names)) for tag, names in attributes.items()
        ),
        styles=frozenset(config.get("RICH_TEXT_ALLOWED_STYLES", ALLOWED_STYLES)),
        url_schemes=frozenset(
            config.get("RICH_TEXT_ALLOWED_URL_SCHEMES", ALLOWED_URL_SCHEMES)
        ),
    )
    return cleaner.clean(html)


@lru_cache(maxsize=8)
def _get_cleaner(
    *,
    tags: frozenset[str],
    attributes: frozenset[tuple[str, frozenset[str]]],
    styles: frozenset[str],
    url_schemes: frozenset[str],
) -> "nh3.Cleaner":
    try:
        import nh3
    except ImportError:
        raise ConfigError(MISSING_NH3_MESSAGE) from None

    allowed = {tag: set(names) for tag, names in attributes}
    allowed[ATTACHMENT_TAG] = set(ATTACHMENT_ATTRIBUTES)
    # nh3 adds `rel` to the links by itself, and refuses to do it
    # if the attribute is also in the allowlist.
    rel_is_allowed = "rel" in allowed.get("a", ()) or "rel" in allowed.get("*", ())

    return nh3.Cleaner(
        tags={*tags, ATTACHMENT_TAG},
        # A tag can't be both allowed and removed with its content
        clean_content_tags=set(CLEAN_CONTENT_TAGS - tags),
        attributes=allowed,
        filter_style_properties=set(styles),
        url_schemes=set(url_schemes),
        link_rel=None if rel_is_allowed else LINK_REL,
    )
