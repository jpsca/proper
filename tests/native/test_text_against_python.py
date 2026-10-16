"""`html2text` (Proper's native code) gives what the same rules give on
Python's own `html.parser.HTMLParser`: thousands of generated HTMLs, valid
and broken. `Reference` is those rules, written on `HTMLParser`."""
import importlib.util
import random
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

import pytest

from proper import _native
from proper.helpers import html2text


SKIP = {"script", "style", "template", "noscript", "iframe", "canvas", "title"}
BLOCKS = {
    "address", "article", "aside", "blockquote", "dd", "details", "dialog", "div", "dl",
    "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
    "h5", "h6", "header", "main", "menu", "nav", "ol", "output", "p", "section", "table",
    "tr", "ul",
}
HTML_SPACE = " \t\n\r\f"


class Writer:
    def __init__(self):
        self.buf = []
        self.pending_nl = 0
        self.pending_space = False
        self.trail_nl = 0
        self.last_cr = False

    def put(self, c):
        self.buf.append(c)
        self.trail_nl = self.trail_nl + 1 if c == "\n" else 0
        self.last_cr = False

    def flush(self):
        if self.pending_nl:
            if self.buf:
                for _ in range(self.pending_nl - self.trail_nl):
                    self.put("\n")
            self.pending_nl = 0
            self.pending_space = False
        elif self.pending_space:
            self.pending_space = False
            self.put(" ")

    def text(self, s):
        for c in s:
            if c in HTML_SPACE:
                if self.buf and not self.pending_nl and not self.trail_nl:
                    self.pending_space = True
            else:
                self.flush()
                self.put(c)

    def literal(self, s, drop_first=False):
        for c in s:
            if drop_first:
                drop_first = False
                if c == "\n":
                    continue
                if c == "\r":
                    self.last_cr = True
                    continue
            if c == "\r":
                self.flush()
                self.put("\n")
                self.last_cr = True
            elif c == "\n":
                if self.last_cr:
                    self.last_cr = False
                else:
                    self.flush()
                    self.put("\n")
            else:
                self.flush()
                self.put(c)

    def block(self):
        self.pending_space = False
        self.pending_nl = max(self.pending_nl, 2)

    def line(self):
        self.pending_space = False
        self.pending_nl = max(self.pending_nl, 1)

    def br(self):
        self.pending_space = False
        self.pending_nl = min(max(self.pending_nl, self.trail_nl) + 1, 2)


def first(attrs, name):
    for key, value in attrs:
        if key == name:
            return value
    return None


class Reference(HTMLParser):
    def __init__(self, attachments):
        super().__init__(convert_charrefs=True)
        self.attachments = attachments
        self.w = Writer()
        self.skip = 0
        self.pre = 0
        self.links = []
        self.drop = False

    def write(self, s):
        if self.pre:
            self.w.literal(s)
        else:
            self.w.text(s)

    def handle_starttag(self, tag, attrs):
        self.drop = False
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        w = self.w
        if tag in BLOCKS:
            w.block()
        elif tag == "br":
            w.br()
        elif tag == "li":
            w.line()
            w.flush()
            w.put("-")
            w.pending_space = True
        elif tag == "hr":
            w.line()
            self.write("-" * 20)
            w.line()
        elif tag == "pre":
            w.block()
            self.write("```")
            w.line()
            self.pre += 1
            self.drop = True
        elif tag == "code":
            if not self.pre:
                w.text("`")
        elif tag == "img":
            alt = first(attrs, "alt")
            if alt:
                self.write(f"[{alt}]")
        elif tag == "proper-attachment":
            label = (
                first(attrs, "alt") or first(attrs, "caption")
                or self.attachments.get(first(attrs, "sgid") or "") or "file"
            )
            self.write(f"[{label}]")
        elif tag == "a":
            self.links.append((first(attrs, "href"), len(w.buf)))

    def handle_endtag(self, tag):
        self.drop = False
        if tag in SKIP:
            if self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        w = self.w
        if tag in BLOCKS:
            w.block()
        elif tag == "li":
            w.line()
        elif tag == "pre":
            if self.pre:
                self.pre -= 1
                w.line()
                self.write("```")
            w.block()
        elif tag == "code":
            if not self.pre:
                w.text("`")
        elif tag == "a" and self.links:
            href, start = self.links.pop()
            if href and "".join(w.buf[start:]).strip(HTML_SPACE) != href:
                self.write(f" ({href})")

    def handle_data(self, data):
        drop, self.drop = self.drop, False
        if self.skip:
            return
        if self.pre:
            self.w.literal(data, drop)
        else:
            self.w.text(data)


def reference(html, attachments=None):
    parser = Reference(attachments or {})
    parser.feed(html)
    parser.close()
    return "".join(parser.w.buf)


# --- generated HTML ---

TAGS = sorted(SKIP | BLOCKS | {
    "a", "br", "li", "hr", "pre", "code", "img", "proper-attachment", "span", "b", "em",
    "xmp", "textarea", "noembed", "noframes", "plaintext", "body", "html", "head",
})
NAMES = ["href", "HREF", "alt", "Alt", "caption", "sgid", "class", "x", "=x", "a'b"]
VALUES = [
    '"https://x.com/a?b=1&amp;c=2"', "'q'", "bare", '"&lt;&#65;&#x42;&notit;&amp=x"',
    '"Logo"', '"photo.jpg"', '"s1"', "s2", '""', "''", '"with > gt"', "'unclosed",
    '"unclosed', "&#0;", "&amp", '" sp  aced "', '"ñandú"', '"&#xD800;"',
]
TEXT = [
    "hola", "Hola mundo", " ", "  ", "\n", "\r\n", "\r", "\t", "\f", "\xa0", "　",
    "ñandú", "日本", "€", "a < b", "x>y", "&amp;", "&amp", "&lt", "&notit;", "&notin;",
    "&#65;", "&#x41", "&#X1F600;", "&#0;", "&#128;", "&#xD800;", "&#1114112;", "&#1;",
    "&#13;", "&#10;", "&", "&#", "&#x", "&;", "&nbsp;", "&ampx", "&AMP;",
    "&CounterClockwiseContourIntegral;", "&" + "a" * 40 + ";", "&Kopf;", "]]>",
    "--", "-->", "https://x.com/a?b=1&amp;c=2", "photo.jpg",
]
MARKUP = [
    "<!-- c -->", "<!---->", "<!-->", "<!--->", "<!-- a --!>", "<!-- unclosed",
    "<!DOCTYPE html>", "<!doctype x", "<!x>", "<![CDATA[ c ]]>", "<![CDATA[ unclosed",
    "<?pi?>", "<?unclosed", "</>", "</ x>", "</1>", "</", "<", "< b", "<1>", "<!",
    "<!-", "</div", "<div", '<a href="x', "<br/>", "<br />", "<BR>", "<hr/>", "<p/>",
    "<pre/>", "<script/>", "<a/>", "</p>", "</li>", "</a>", "</pre>", "</code>",
    "</script>", "</style>", "</title>", "</textarea>", "</xmp>", "</SCRIPT >",
    "</script x='>'>", "<blocKquote>", "</blocKquote>", "<DİV>",
]


def random_tag(rnd):
    name = rnd.choice(TAGS)
    if rnd.random() < 0.2:
        name = name.upper()
    attrs = ""
    for _ in range(rnd.randrange(0, 3)):
        sep = rnd.choice([" ", "  ", "\n", "/", " / ", "\t"])
        attr = rnd.choice(NAMES)
        if rnd.random() < 0.8:
            attr += rnd.choice(["=", " = ", "= ", " ="]) + rnd.choice(VALUES)
        attrs += sep + attr
    end = rnd.choice([">", ">", " >", "/>", " />", "", "\n>"])
    if rnd.random() < 0.5:
        return f"<{name}{attrs}{end}"
    return f"</{name}{rnd.choice(['', ' ', ' x=1'])}>"


def well_formed(rnd):
    """A link, an image, an attachment, a list or a pre, closed."""
    text = rnd.choice(TEXT)
    value = rnd.choice(VALUES)
    return rnd.choice([
        f"<a href={value}>{text}</a>",
        f"<a href={value}>{value.strip(chr(34) + chr(39))}</a>",
        f"<a href={value}><b>{text}</b> {rnd.choice(TEXT)}</a>",
        f"<img src=a.png alt={value}>",
        f"<proper-attachment sgid={rnd.choice(['s1', 's2', 'none', chr(34) * 2])}"
        f"{rnd.choice(['', ' alt=' + value, ' caption=' + value])}></proper-attachment>",
        f"<ul><li>{text}</li><li>{rnd.choice(TEXT)}</ul>",
        f"<pre>{rnd.choice(['', chr(10), chr(13) + chr(10)])}{text}{rnd.choice(TEXT)}</pre>",
    ])


def random_html(rnd):
    pieces = []
    for _ in range(rnd.randrange(0, 25)):
        r = rnd.random()
        if r < 0.4:
            pieces.append(rnd.choice(TEXT))
        elif r < 0.75:
            pieces.append(random_tag(rnd))
        elif r < 0.88:
            pieces.append(well_formed(rnd))
        else:
            pieces.append(rnd.choice(MARKUP))
    return "".join(pieces)


ATTACHMENTS = {"s1": "photo.jpg", "s2": "", "": "empty-sgid.txt"}


def check(html):
    assert html2text(html, ATTACHMENTS) == reference(html, ATTACHMENTS), repr(html)


@pytest.mark.parametrize("seed", range(8))
def test_generated_html(seed):
    rnd = random.Random(seed)
    for _ in range(3000):
        check(random_html(rnd))


@pytest.mark.parametrize("seed", range(4))
def test_cut_and_changed(seed):
    rnd = random.Random(f"cut{seed}")
    for _ in range(2000):
        html = random_html(rnd)
        i = rnd.randrange(0, len(html) + 1)
        kind = rnd.randrange(3)
        if kind == 0:
            html = html[:i]
        elif kind == 1:
            html = html[:i] + rnd.choice("<>&;\"'/=-!\r\n ") + html[i:]
        else:
            html = html[:i] + html[i + 1:]
        check(html)


@pytest.mark.parametrize("html", [
    "",
    "<pre>\nfirst\n</pre>",
    "<pre>\r\nfirst\r\n\r\nsecond\r</pre>",
    "<pre><code>\nx = 1</code></pre>",
    "<pre><!-- c -->\nx</pre>",
    "<pre>&#10;x</pre>",
    "<pre>a\r<!-- -->\nb</pre>",
    "a<br><br><br>b",
    "<p>a</p><br><p>b</p>",
    "<ul><li>one<li>two</ul>",
    "<li></li><li>x</li>",
    '<a href="https://x.com">https://x.com</a>',
    '<a href="https://x.com"> https://x.com </a>',
    '<a href="x"><a href="y">in</a>out</a>',
    '<a href="x">',
    "<a>no href</a>",
    '<a href="">empty</a>',
    '<a href="x"><img alt="Logo"></a>',
    '<a href="x"></a>',
    "<script>a</b> <p>x</p></script>after",
    "<script>never closed <p>x</p>",
    "<textarea>&lt;b&gt; &amp</textarea>",
    "<title>T &amp; t</title>body",
    "<xmp>&lt;raw</xmp>",
    "<plaintext><p>&amp; all raw",
    "<noscript><p>x</p><style>s</style></noscript>after",
    "<head><title>T</title></head><body>B</body>",
    '<proper-attachment sgid="s1"></proper-attachment>',
    '<proper-attachment sgid="s1" alt="" caption="Cap">',
    '<proper-attachment sgid="s2">',
    "<proper-attachment>",
    '<proper-attachment sgid="nope"/>',
    "&#" + "9" * 4000 + ";",
    "<p>" * 100 + "deep" + "</p>" * 100,
    "<a href=x>" * 300 + "many links" + "</a>" * 300,
])
def test_the_edges(html):
    check(html)


def test_large_html():
    rnd = random.Random("large")
    html = "".join(random_html(rnd) for _ in range(3000))
    check(html)


def test_more_than_the_buffers():
    """A new thread starts with buffers of `BUFFER_SIZE`: an HTML larger than
    that, whose text is larger still (an `<hr>` is 20 `-`), and more links
    open at once than there is room for."""
    html = "<a href=x>" * (_native.LINKS * 2) + "<hr>" * _native.BUFFER_SIZE
    with ThreadPoolExecutor(1) as pool:
        text = pool.submit(html2text, html).result()
    assert text == reference(html)


def test_the_entities_are_python_s():
    """`proper_entities.inc` is what `gen_entities.py` makes from this
    Python's `html.entities.html5`."""
    path = Path(_native.__file__).parent / "gen_entities.py"
    spec = importlib.util.spec_from_file_location("gen_entities", path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert (path.parent / "proper_entities.inc").read_text() == gen.generate()
