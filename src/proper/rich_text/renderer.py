"""Server-side rendering of stored rich text HTML.

The editor (Lexxy) emits HTML directly, so the framework no longer needs
a structural walker — paragraphs, headings, lists, links and inline
marks ship from the client already formed. The one piece the server owns
is the attachment expansion: each `<proper-attachment sgid="..."></proper-attachment>`
tag is a placeholder that must be replaced by the rendered
`rich_text_attachment.jx` partial for the referenced `Attachment` row.

`replace_attachments(html, resolver)` is the entry point. The resolver
is called with the parsed attribute dict of each tag and returns the
HTML to substitute. If the resolver returns an empty string, the tag is
dropped entirely (useful when the referenced attachment no longer exists).
"""
import re
from collections.abc import Callable


AttachmentRenderer = Callable[[dict[str, str]], str]


# TODO: server-side HTML sanitization. The HTML arrives pre-formatted from
# Lexxy; before production we should pass it through nh3/bleach with an
# allowlist that includes `<proper-attachment>` + every tag Lexxy emits.
_ATTACHMENT_TAG_RE = re.compile(
    r"<proper-attachment\b([^>]*)>(.*?)</proper-attachment>",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r'([a-zA-Z][a-zA-Z0-9_-]*)\s*=\s*"([^"]*)"')


def replace_attachments(
    html: str,
    attachment_renderer: AttachmentRenderer | None = None,
) -> str:
    """Return `html` with each `<proper-attachment>` tag substituted by
    the output of `attachment_renderer(attrs)`. If the renderer is
    `None`, tags collapse to empty strings.
    """
    if not isinstance(html, str) or not html:
        return ""

    if attachment_renderer is None:
        return _ATTACHMENT_TAG_RE.sub("", html)

    def _sub(match: re.Match[str]) -> str:
        attrs = {name.lower(): value for name, value in _ATTR_RE.findall(match.group(1))}
        return attachment_renderer(attrs) or ""

    return _ATTACHMENT_TAG_RE.sub(_sub, html)
