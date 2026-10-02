# The HTML of a rich text document is sanitized when it is rendered:
# only what is listed in this file is kept. What is stored is not changed,
# so you can edit these lists at any time.
#
# Set this to False to render the documents as they are stored.
# Do it only if every author of rich text in your app is trusted.
RICH_TEXT_SANITIZE = True

# The <proper-attachment> tags are always allowed.
RICH_TEXT_ALLOWED_TAGS = [
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
]

# Attributes allowed for each tag. The ones under "*" are allowed in all.
# Don't add "data-controller" or "data-action": the document could then run
# the Stimulus controllers of your app.
RICH_TEXT_ALLOWED_ATTRIBUTES = {
    "*": ["class", "style", "title"],
    "a": ["href"],
    "img": ["src", "alt", "width", "height"],
    "li": ["value"],
    "ol": ["start"],
    "pre": ["data-language", "data-highlight-language"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}

# CSS properties kept in a "style" attribute. The rest are removed.
RICH_TEXT_ALLOWED_STYLES = ["color", "background-color"]

# URL schemes allowed in attributes like "href" and "src".
# Relative URLs are always allowed.
RICH_TEXT_ALLOWED_URL_SCHEMES = ["http", "https", "mailto", "tel"]
