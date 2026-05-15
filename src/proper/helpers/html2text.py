"""A very simple HTML to plain-text converter."""

import re
from html.entities import name2codepoint


__all__ = ["html2text"]

rx_body = re.compile(r".*<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)
rx_comments = re.compile(r"<!--(.*?)-->", re.DOTALL)

# Insert a newline before block-level tags
blocktags = [
    "address",
    "article",
    "aside",
    "blockquote",
    "dd",
    "details",
    "dialog",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "main",
    "menu",
    "nav",
    "output",
    "p",
    "section",
    "table",
]
rx_blocktags = re.compile(rf"[\n\s]*</?({'|'.join(blocktags)})[^>]*>[\n\s]*", re.IGNORECASE)

# Remove these tags and their contents
ignoretags = [
    "canvas",
    "iframe",
    "noscript",
    "script",
    "style",
    "template",
]
rx_ignoretags = re.compile(
    rf"<({'|'.join(ignoretags)})[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL
)

rx_links = re.compile(
    r'<a [^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)
rx_images = re.compile(
    r'<img [^>]*src=["\'](.*?)["\'][^>]*/?>', re.IGNORECASE | re.DOTALL
)
rx_breaks = re.compile(r"[\n\s]*<br\s*/?>[\n\s]*", re.IGNORECASE)
rx_listitems = re.compile(r"[\n\s]*<li\s*/?>[\n\s]*", re.IGNORECASE)
rx_lines = re.compile(r"[\n\s]*<hr\s*/?>[\n\s]*", re.IGNORECASE)
rx_code = re.compile(r"</?code[^>]*>", re.IGNORECASE)
rx_pre = re.compile(r"[\n\s]*</?pre[^>]*>[\n\s]*", re.IGNORECASE)

# Remove the remaining tags but leave their contents
rx_tags = re.compile(r"</?[^>]+>", re.IGNORECASE | re.DOTALL)


def get_body(html):
    match = rx_body.match(html)
    if match:
        html = match.group(1)
    return html.strip()


def remove_comments(html):
    return rx_comments.sub("", html)


def remove_ignoretags(html):
    return rx_ignoretags.sub("", html)


def replace_links(html):
    def fixup(m):
        href = m.group(1)
        text = m.group(2)
        if href == text or href == "":
            return text
        else:
            return f"{text} ({href})"

    return rx_links.sub(fixup, html)


def replace_images(html):
    def fixup(m):
        src = m.group(1)
        return src

    return rx_images.sub(fixup, html)


def replace_listitems(html):
    return rx_listitems.sub("\n- ", html)


def replace_breaks(html):
    return rx_breaks.sub("\n", html)


def replace_lines(html):
    return rx_lines.sub("\n" + ("-" * 20) + "\n", html)


def replace_codetags(html):
    return rx_code.sub("`", html)


def replace_pretags(html):
    return rx_pre.sub("\n```\n", html)


def replace_blocktags(html):
    return rx_blocktags.sub("\n\n", html)


def remove_tags(html):
    return re.sub(rx_tags, "", html)


def unescape(html):
    def fixup(m):
        html = m.group(0)
        if html[:2] == "&#":
            try:
                if html[:3] == "&#x":
                    return chr(int(html[3:-1], 16))
                else:
                    return chr(int(html[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                html = chr(name2codepoint[html[1:-1]])
            except KeyError:
                pass
        return html  # leave as is

    return re.sub(r"&#?\w+;", fixup, html)


def remove_extra_newlines(text):
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text.strip()


def html2text(html):
    """Convert HTML to plain text."""
    html = get_body(html)
    html = remove_comments(html)
    html = remove_ignoretags(html)
    html = replace_links(html)
    html = replace_images(html)
    html = replace_listitems(html)
    html = replace_breaks(html)
    html = replace_lines(html)
    html = replace_codetags(html)
    html = replace_pretags(html)
    html = replace_blocktags(html)
    html = remove_tags(html)
    html = unescape(html)
    html = remove_extra_newlines(html)
    return html.strip()
