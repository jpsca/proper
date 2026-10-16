"""
Whitespace handling must match Jx exactly, not just after collapsing:

- Jinja's whitespace control (`{%-`, `-%}`, `{{-`, `-}}`, `{#-`, `-#}`),
  newline normalisation and removal of the trailing newline;
- Jx's own rules: a component's output starts with no whitespace, component
  content is stripped, and slot/fill markers apply to their bodies.
"""

import random

import pytest


def exact(project, files, template="page.jx", **kwargs):
    project.write(files)
    mini = project.render_mini(template, **kwargs)
    jx = str(project.render_jx(template, **kwargs))
    assert mini == jx, f"\nminijx: {mini!r}\njx:     {jx!r}"
    return mini


CASES = {
    "leading whitespace of a component": "\n\n   <p>x</p>",
    "header then body": '{# def a="x" #}\n\n<p>{{ a }}</p>\n',
    "header markers": '{#- def a="x" -#}\n\n  <p>{{ a }}</p>',
    "trailing newline dropped once": "<p>x</p>\n\n",
    "crlf": "<p>\r\n  x\r\n</p>\r\n",
    "lone cr": "a\rb\r",
    "expr markers": "<p>  {{- 1 -}}  </p> [ {{- 2 }} ] [ {{ 3 -}} ]",
    "comment markers": "a  {#- c -#}  b  {# d -#}  c  {#- e #}  d",
    "comment is a boundary": "a  {# c #}  {%- if true %}x{% endif %}",
    "if markers": "[  {%- if true -%}  yes  {%- else -%}  no  {%- endif -%}  ]",
    "elif markers": "[ {% if false %} a {%- elif true -%} b {% else %} c {% endif %} ]",
    "for markers": "[ {%- for i in [1, 2] -%} ( {{ i }} ) {%- endfor %} ]",
    "for else markers": "[ {% for i in [] %} x {%- else -%} empty {%- endfor -%} ]",
    "set and do": "a  {%- set x = 1 -%}  b  {% do [].append(1) -%}  c",
    "filter markers": "[ {%- filter upper -%}  abc  {%- endfilter -%} ]",
    "raw markers": "[  {%- raw -%}  {{ x }}  {%- endraw -%}  ]",
    "raw is a boundary": "{% raw %}a  {% endraw %}   {%- if true %}x{% endif %}",
    "plus markers do nothing": "[  {%+ if true +%}  x  {%+ endif +%}  ]",
}


@pytest.mark.parametrize("source", CASES.values(), ids=CASES.keys())
def test_template_whitespace(project, source):
    exact(project, {"page.jx": source})


def test_component_content_is_stripped(project):
    exact(project, {
        "box.jx": "<div>[{{ content }}]</div>",
        "page.jx": '{# import "box.jx" as Box #}\n<Box>\n   hello   \n</Box>|<Box>  </Box>|<Box />',
    })


def test_child_output_starts_without_whitespace(project):
    exact(project, {
        "item.jx": "{# def v #}\n\n   <li>{{ v }}</li>\n",
        "page.jx": '{# import "item.jx" as Item #}<ul>{% for v in [1, 2] %} <Item v={{ v }} /> {% endfor %}</ul>',
    })


def test_slots_and_fills(project):
    exact(project, {
        "card.jx": """<div>
  {%- slot head -%}
    default head
  {%- endslot -%}
  |{% slot body %}  body default  {% endslot %}|
  {{ content }}
</div>""",
        "page.jx": """{# import "card.jx" as Card #}
<Card>
  before
  {%- fill head -%}
     filled head
  {%- endfill -%}
  middle
  {% fill body %}  kept  {% endfill %}
  after
</Card>""",
    })


def test_whitespace_between_comments_is_content(project):
    """Only the ends of the content are stripped (found by the random test, seed 961)."""
    exact(project, {
        "child.jx": "[{{ content }}]",
        "page.jx": '{# import "child.jx" as Child #}<Child>{# a #} {# b #}</Child><Child>{# a #}</Child><Child>  </Child>',
    })


def test_markers_around_fills_join_the_text_around_them(project):
    """Jx moves fills out, so the text on both sides becomes one piece."""
    exact(project, {
        "card.jx": "<div>{% slot a %}{% endslot %}|{{ content }}|</div>",
        "page.jx": """{# import "card.jx" as Card #}
<Card>
  {% if true %}x{% endif -%}
  {% fill a %}A{% endfill %}
     y   {%- if true %}z{% endif %}
</Card>""",
    })


# Random templates


MARKS = ["", "", "-", "+"]
TEXTS = ["", " ", "  ", "\n", " \n ", "\t", "a", " b ", "\n c \n", "d\n\n"]


class Gen:
    def __init__(self, rng: random.Random, component: bool, slot: bool):
        self.rng = rng
        self.component = component
        self.slot = slot

    def m(self):
        return self.rng.choice(MARKS)

    def dash(self):
        return self.rng.choice(["", "", "-"])

    def text(self):
        return self.rng.choice(TEXTS)

    def body(self, depth: int) -> str:
        return "".join(self.piece(depth) for _ in range(self.rng.randint(0, 4)))

    def piece(self, depth: int) -> str:
        r = self.rng
        kinds = ["text", "text", "expr", "comment", "set"]
        if depth > 0:
            kinds += ["if", "for", "filter", "raw"]
            if self.component:
                kinds += ["comp", "comp"]
            if self.slot:
                kinds += ["slot"]
        kind = r.choice(kinds)
        t, d = self.text, depth - 1
        if kind == "text":
            return t()
        if kind == "expr":
            return f"{t()}{{{{{self.dash()} {r.choice(['1', 'x', '"s"'])} {self.dash()}}}}}{t()}"
        if kind == "comment":
            return f"{t()}{{#{self.dash()} c {self.dash()}#}}{t()}"
        if kind == "set":
            return f"{t()}{{%{self.m()} set y = 2 {self.m()}%}}{t()}"
        if kind == "if":
            cond = r.choice(["true", "false"])
            out = f"{{%{self.m()} if {cond} {self.m()}%}}{self.body(d)}"
            if r.random() < 0.5:
                out += f"{{%{self.m()} else {self.m()}%}}{self.body(d)}"
            return t() + out + f"{{%{self.m()} endif {self.m()}%}}" + t()
        if kind == "for":
            seq = r.choice(["[1, 2]", "[]"])
            out = f"{{%{self.m()} for i in {seq} {self.m()}%}}{self.body(d)}"
            if r.random() < 0.5:
                out += f"{{%{self.m()} else {self.m()}%}}{self.body(d)}"
            return t() + out + f"{{%{self.m()} endfor {self.m()}%}}" + t()
        if kind == "filter":
            return t() + f"{{%{self.m()} filter upper {self.m()}%}}{self.body(d)}{{%{self.m()} endfilter {self.m()}%}}" + t()
        if kind == "raw":
            # Jinja does not accept `raw +%}`
            return t() + f"{{%{self.m()} raw {self.dash()}%}}{t()}{{{{ r }}}}{t()}{{%{self.m()} endraw {self.m()}%}}" + t()
        if kind == "slot":
            return t() + f"{{%{self.m()} slot s {self.m()}%}}{self.body(d)}{{%{self.m()} endslot {self.m()}%}}" + t()
        # component use, maybe with content and a fill
        if r.random() < 0.3:
            return t() + "<Child />" + t()
        inner = [self.body(d)]
        if r.random() < 0.6:
            fill = Gen(r, component=False, slot=False).body(d)
            inner.append(f"{{%{self.m()} fill s {self.m()}%}}{fill}{{%{self.m()} endfill {self.m()}%}}")
            inner.append(self.body(d))
        return t() + "<Child>" + "".join(inner) + "</Child>" + t()


def header(rng: random.Random, decl: str) -> str:
    return rng.choice(["", "\n", "  "]) + rng.choice([f"{{# {decl} #}}", f"{{#- {decl} -#}}"]) + rng.choice(["", "\n", "\n\n  "])


@pytest.mark.parametrize("seed", range(300))
def test_random_templates(project, seed):
    rng = random.Random(seed)
    child = header(rng, 'def x="X"') + Gen(rng, component=False, slot=True).body(3) + "[{{ content }}]"
    page = (
        header(rng, 'import "child.jx" as Child')
        + header(rng, 'def x="P"')
        + Gen(rng, component=True, slot=False).body(3)
    )
    files = {"child.jx": child, "page.jx": page}
    if rng.random() < 0.2:
        files = {k: v.replace("\n", "\r\n") for k, v in files.items()}
    if rng.random() < 0.5:
        files = {k: v + "\n" for k, v in files.items()}
    try:
        exact(project, files)
    except AssertionError as err:
        raise AssertionError(f"seed {seed}\nchild.jx: {child!r}\npage.jx: {page!r}\n{err}") from None
