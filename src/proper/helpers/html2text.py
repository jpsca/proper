"""HTML to plain text: the text version of an HTML email, and `str()` of a
rich text document. The work is done by Proper's native code
(`proper/_native/proper_text.pas`)."""
import typing as t

from .. import _native


__all__ = ["html2text"]


def html2text(html: str, attachments: "t.Mapping[str, str] | None" = None) -> str:
    """The text of an HTML, without its tags.

    The HTML is read as Python's `html.parser.HTMLParser` reads it, with its
    character references decoded. Then:

    - The text of `script`, `style`, `template`, `noscript`, `iframe`,
      `canvas` and `title` is dropped.
    - A block (`p`, `div`, `h1` to `h6`, `blockquote`, `ul`, `ol`, `table`,
      `tr`, `section`, ...) is separated from the rest by a blank line.
    - `<li>` starts a line with `- `, `<br>` starts a new line, and `<hr>`
      is a line of 20 `-`.
    - `<pre>` keeps its text as it is, between lines of three backticks;
      `<code>` puts its text between backticks.
    - A link is its text and, in parentheses, its `href`, unless the
      `href` is the same as the text: `Ver (https://example.com)`.
    - An image with an `alt` is `[alt]`. A `<proper-attachment>` is its
      `alt`, its `caption`, or the file name of its `sgid` in `attachments`,
      in brackets: `[photo.jpg]`, or `[file]` without any of them.
    - Out of a `<pre>`, spaces, tabs and new lines in a row are one space;
      there are no spaces at the start or the end of a line, no more than
      one blank line in a row, and no blank lines at the start or the end.

    Arguments:
        html:
            The HTML.
        attachments:
            The file name of each attachment, by its `sgid`.

    """
    if not html:
        return ""
    filenames = {
        sgid.encode("utf-8", "surrogatepass"): name.encode("utf-8", "surrogatepass")
        for sgid, name in (attachments or {}).items()
    }
    text = _native.html2text(html.encode("utf-8", "surrogatepass"), filenames)
    return text.decode("utf-8", "surrogatepass")
