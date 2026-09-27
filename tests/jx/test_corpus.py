"""
Jx | Copyright (c) Juan-Pablo Scaletti

A corpus of awkward and broken templates. Every one of them has to parse to the
same answer it does today, and everything the emitter writes has to be valid
Jinja — a parser can be wrong in ways no single hand-written test predicts, so
the point is breadth.
"""

from pathlib import Path

import jinja2
import pytest

from proper.jx.exceptions import TemplateSyntaxError
from proper.jx.meta import extract_metadata
from proper.jx.parser import JxParser


REPO = Path(__file__).parent.parent
DOCS_VIEWS = sorted((REPO / "docs" / "views").glob("*.jx"))
JINJA = jinja2.Environment()


def emit(name: str, source: str, components: list[str]) -> str:
    """Parse, and check the generated source is Jinja the compiler accepts."""
    out, _ = JxParser(name=name, source=source, components=components).parse()
    JINJA.parse(out)
    return out


@pytest.mark.skipif(not DOCS_VIEWS, reason="no .jx files on disk")
@pytest.mark.parametrize("path", DOCS_VIEWS, ids=lambda p: p.name)
def test_docs_views(path):
    """The real templates that build the Jx documentation site."""
    source = path.read_text(encoding="utf-8")
    meta = extract_metadata(source, base_path=path.parent, fullpath=path)
    emit(path.name, source, list(meta.imports.keys()))


AWKWARD = {
    "empty": "",
    "text only": "just some text, no tags at all",
    "lone lt": "a < b and c > d",
    "lowercase tag": "<div class='x'>hello</div>",
    "tag lookalike in text": "use <Card /> like this",
    "self closing": "<Card />",
    "self closing no space": "<Card/>",
    "attr with slash": '<Card href="http://a/b" />',
    "attr with gt in string": '<Card label="a > b" />',
    "attr with lt in string": '<Card label="a < b" />',
    "expr attr with braces": '<Card data="{{ {\'a\': 1} }}" />',
    "expr attr with quotes": '<Card label="{{ x if y else \'a>b\' }}" />',
    "expr attr with rbrace in string": "<Card label={{ '}}' }} />",
    "flag attrs": "<Card green large />",
    "multiline attrs": '<Card\n  a="1"\n  b="2"\n>x</Card>',
    "nested same tag": "<Card><Card>inner</Card></Card>",
    "nested same tag siblings": "<Card><Card>a</Card><Card>b</Card></Card>",
    "nested self closing inside": "<Card><Card />after</Card>",
    "comment hides tag": "{# <Card /> #}<Card />",
    "raw hides tag": "{% raw %}<Card />{% endraw %}<Card />",
    "raw hides fill": "{% raw %}{% fill x %}{% endfill %}{% endraw %}",
    "empty raw": "{% raw %}{% endraw %}<Card />",
    "raw with dashes": "{%- raw -%}<Card />{%- endraw -%}",
    "raw with plus": "{% raw %}<Card />{%+ endraw %}",
    "plus block": "{%+ if x %}<Card />{%+ endif %}",
    "plus for": "{% for i in x %}<Card />{%+ endfor %}",
    "plus slot": "{%+ slot a %}d{%+ endslot %}",
    "raw hides a bare block start": "{% raw %}Use {% in a sentence{% endraw %}<Card />",
    "raw hides an unterminated quote": '{% raw %}{% "oops{% endraw %}<Card />',
    "slot basic": "{% slot header %}default{% endslot %}",
    "slot empty default": "{% slot header %}{% endslot %}",
    "slot strip": "{% slot header -%}  x  {%- endslot %}",
    "two slots": "{% slot a %}A{% endslot %}{% slot b %}B{% endslot %}",
    "fill basic": "<Card>{% fill a %}A{% endfill %}main</Card>",
    "fill only": "<Card>{% fill a %}A{% endfill %}</Card>",
    "fill empty": "<Card>{% fill a %}{% endfill %}main</Card>",
    "fill strip": "<Card>{% fill a -%} A {%- endfill %}main</Card>",
    "fills nested components": (
        "<Card>{% fill a %}<Card>{% fill b %}in{% endfill %}x</Card>{% endfill %}out</Card>"
    ),
    "fill inside for": "{% for i in x %}<Card>{% fill a %}{{ i }}{% endfill %}</Card>{% endfor %}",
    "component inside if": "{% if x %}<Card />{% endif %}",
    "expr with filter": '<Card title="{{ x | title }}" />',
    "expr with pipe in string": "<Card title=\"{{ 'a|b' }}\" />",
    "dotted tag name": "<Ui.Card />",
    "dashed attr": '<Card data-foo="1" />',
    "colon attr": '<Card :bind="x" />',
    "at attr": '<Card @click="go()" />',
    "unicode text": "<Card>ñandú 日本語 🎉</Card>",
    "crlf": '<Card\r\n  a="1"\r\n>x</Card>',
    "deep nesting": "<Card>" * 5 + "x" + "</Card>" * 5,
}

BROKEN = {
    "unclosed component": "<Card>never closed",
    "unknown component": "<Nope />",
    "unclosed quote": '<Card a="unterminated>x</Card>',
    "unclosed expr": "<Card a={{ x />",
    "stray close": "</Card>",
}


@pytest.mark.parametrize("name", list(AWKWARD), ids=list(AWKWARD))
def test_awkward_input(name):
    emit(name, AWKWARD[name], ["Card", "Ui.Card"])


@pytest.mark.parametrize("name", list(BROKEN), ids=list(BROKEN))
def test_broken_input(name):
    with pytest.raises(TemplateSyntaxError):
        JxParser(name=name, source=BROKEN[name], components=["Card"]).parse()
