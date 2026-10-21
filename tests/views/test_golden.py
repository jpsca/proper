"""
Golden tests: the generated Python must produce the same HTML as Jx does,
ignoring whitespace.
"""

import pytest


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_text_and_output(project):
    project.write({"a.jx": "{# def name, n=2 #}<p>Hi {{ name }}, {{ n + 1 }} {{ 'x' ~ n }}</p>"})
    project.assert_same("a.jx", name="Ana")


def test_if_elif_else(project):
    project.write({
        "a.jx": """{# def n #}
{% if n > 10 %}big{% elif n > 5 %}mid{% elif n == 5 %}five{% else %}small{% endif %}
{% if n %}truthy{% endif %}{% if not n %}falsy{% endif %}
"""
    })
    for n in (0, 3, 5, 7, 20):
        project.assert_same("a.jx", n=n)


def test_for_with_loop_vars(project):
    project.write({
        "a.jx": """{# def items #}
<ul>
{% for it in items %}
  <li class="{{ loop.cycle('a', 'b', 'c') }}">
    {{ loop.index }} {{ loop.index0 }} {{ loop.revindex }} {{ loop.revindex0 }} {{ loop.length }}
    {{ loop.first }} {{ loop.last }}{% if not loop.first %} prev={{ loop.previtem }}{% endif %}{% if not loop.last %} next={{ loop.nextitem }}{% endif %}
    {{ it }}{% if loop.changed(it[0]) %} changed{% endif %}
  </li>
{% endfor %}
</ul>
"""
    })
    project.assert_same("a.jx", items=["apple", "avocado", "banana", "cherry", "coconut"])


def test_for_else_and_filter(project):
    project.write({
        "a.jx": """{# def items #}
{% for x in items if x % 2 == 0 %}{{ loop.index }}:{{ x }} {% else %}none{% endfor %}
{% for a, b in items | batch(2, 0) %}[{{ a }}-{{ b }}]{% endfor %}
"""
    })
    project.assert_same("a.jx", items=[1, 2, 3, 4, 6])
    project.assert_same("a.jx", items=[1, 3])
    project.assert_same("a.jx", items=[])


def test_nested_loops_keep_outer_loop(project):
    project.write({
        "a.jx": """{# def rows #}
{% for row in rows %}
  {% for cell in row %}{{ loop.index }}{% endfor %}
  outer={{ loop.index }}/{{ loop.length }}
{% endfor %}
"""
    })
    project.assert_same("a.jx", rows=[[1, 2], [3], [4, 5, 6]])


def test_recursive_for(project):
    project.write({
        "a.jx": """{# def nodes #}
<ul>{% for n in nodes recursive %}<li>{{ n.name }} d{{ loop.depth }}{% if n.kids %}<ul>{{ loop(n.kids) }}</ul>{% endif %}</li>{% endfor %}</ul>
"""
    })
    nodes = [
        {"name": "r", "kids": [{"name": "c1", "kids": []}, {"name": "c2", "kids": [{"name": "g", "kids": []}]}]},
        {"name": "s", "kids": []},
    ]
    project.assert_same("a.jx", nodes=nodes)


def test_set_do_filter_raw_comment(project):
    project.write({
        "a.jx": """{# def items #}
{% set total = items | length %}
{% set label = "n=" ~ total %}
{% do items.append(99) %}
{{ label }} {{ items | join(",") }}
{% filter upper %}shout {{ label }}{% endfilter %}
{% filter trim | replace("a", "4") | title %}   banana split   {% endfilter %}
{% raw %}{{ not rendered }}{% if x %}{% endraw %}
{# comment #}done
"""
    })
    project.assert_same("a.jx", items=[1, 2])


def test_expressions(project):
    project.write({
        "a.jx": """{# def d, l, s, n #}
{{ d.a }} {{ d["b"] }} {{ l.0 }} {{ l[-1] }} {{ l[1:3] | join("|") }} {{ s[::-1] }}
{{ n ** 2 }} {{ n // 3 }} {{ n % 3 }} {{ -n }} {{ n * 2 + 1 }} {{ (n + 1) * 2 }}
{{ 1 < n < 10 }} {{ n in l }} {{ n not in l }} {{ n == 7 and true or false }}
{{ "yes" if n > 5 else "no" }} [{{ "only" if n > 100 }}] {{ "a" "b" "c" }} {{ [1, 2, 3] | length }} {{ {"k": n}["k"] }}
{{ (1, 2) | join("-") }} {{ none is none }} {{ true }} {{ false }} {{ 1.5 + 1 }}
{{ n is odd }} {{ n is divisibleby 7 }} {{ n is not even }} {{ s is string }} {{ l is sequence }} {{ d is mapping }}
{{ n is sameas n }} {{ 3 is in l }} {{ n is eq 7 }} {{ n is gt 5 }} {{ 2 is lt 1 }}
{{ range(3) | list }} {{ d | dictsort }} {{ d.items() | list }}
"""
    })
    project.assert_same("a.jx", d={"a": 1, "b": 2}, l=[3, 7, 9, 11], s="hello", n=7)


def test_globals_defined_and_default(project):
    project.write({
        "a.jx": """{# def x=1 #}
{{ site.name }} {{ helper(x) }}
{% if site is defined %}site{% endif %}{% if nope is defined %}bad{% endif %}{% if nope is undefined %}undef{% endif %}
{{ nope | default("dflt") }} {{ site.missing | default("m") }} {{ site["nope"] | default("i") }}
{{ site.name is defined }} {{ site.zzz is defined }} {{ x is defined }}
"""
    })
    g = {"site": {"name": "S"}, "helper": lambda v: v * 10}
    project.assert_same("a.jx", globals=g)


def test_components_attrs_content_slots(project):
    project.write({
        "ui/button.jx": """{# def text="Click", kind="primary" #}
<button {{ attrs.render(class="btn btn-" ~ kind, type="button") }}>{{ text }}</button>
""",
        "card.jx": """{# import "ui/button.jx" as Button #}
{# def title, footer=true #}
{% do attrs.setdefault(role="region") %}
{% do attrs.add_class("card") %}
<section {{ attrs.render() }}>
  <h2>{{ title }}</h2>
  <div class="body">{{ content }}</div>
  {% slot footer %}<Button text="Default" />{% endslot %}
  {% slot extra %}{% endslot %}
</section>
""",
        "page.jx": """{# import "./card.jx" as Card #}
{# import "ui/button.jx" as Button #}
{# def user, kinds #}
<Card title="Hello" id="c1" class="wide" data-user={{ user.name }}>
  {% fill footer %}<Button text={{ user.name }} kind="danger" disabled aria-label="x" />{% endfill %}
  <p>Welcome {{ user.name }}</p>
</Card>
<Card title={{ "Bye " ~ user.name }} hidden />
{% for k in kinds %}<Button kind={{ k }} text="{{ k }}" class={{ "k-" ~ loop.index }} />{% endfor %}
"""
    })
    project.assert_same("page.jx", user=Obj(name="Ana"), kinds=["a", "b"])


def test_attrs_forwarding_and_methods(project):
    project.write({
        "inner.jx": """{# def label #}
<span {{ attrs.render(class="inner") }}>{{ label }} {{ attrs.get("title", "no-title") }} {{ attrs.classes }}</span>
{% if "on" in attrs.classes %}ON{% endif %}
""",
        "outer.jx": """{# import "inner.jx" as Inner #}
{# def label #}
{% do attrs.remove_class("gone") %}
{% do attrs.prepend_class("first") %}
{% do attrs.set(data_x="1", hidden=false) %}
<Inner label={{ label }} attrs={{ attrs }} />
"""
    })
    project.assert_same("outer.jx", label="L", **{"class": "on gone b", "title": "T", "hidden": True, "id": "i"})
    project.assert_same("outer.jx", label="L")


def test_self_recursive_component(project):
    project.write({
        "node.jx": """{# import "./node.jx" as Node #}
{# def item, level=1 #}
<div class="l{{ level }}">{{ item.name }}
{% for child in item.kids %}<Node item={{ child }} level={{ level + 1 }} />{% endfor %}
</div>
"""
    })
    item = {"name": "a", "kids": [{"name": "b", "kids": [{"name": "c", "kids": []}]}, {"name": "d", "kids": []}]}
    project.assert_same("node.jx", item=item)


def test_escape_filter_only(project):
    project.write({"a.jx": "{# def s #}{{ s }} | {{ s | escape }} | {{ s | e }} | {{ s | safe }}"})
    html = project.render_mini("a.jx", s='<b class="x">&</b>')
    escaped = "&lt;b class=&#34;x&#34;&gt;&amp;&lt;/b&gt;"
    # without autoescape, only the filters escape; with it, `{{ s }}` too,
    # and `escape` does not escape again
    first = escaped if project.autoescape else '<b class="x">&</b>'
    assert html == f'{first} | {escaped} | {escaped} | <b class="x">&</b>'


def test_css_js_constants(project):
    project.write({
        "a.jx": '{# import "b.jx" as B #}{# css "a.css", "shared.css" #}{# js "a.js" #}<B />',
        "b.jx": '{# css "b.css" #}{# css shared.css #}{# js "b.js" #}b',
    })
    project.render_mini("a.jx")
    from .helpers import load_module

    mod = load_module(project.mini / "a.py")
    assert mod.CSS == ("a.css", "shared.css", "b.css")
    assert mod.JS == ("a.js", "b.js")
    from proper.views import Catalog

    co = Catalog(project.mini).get_component("a.jx")
    assert co.collect_css() == ["a.css", "shared.css", "b.css"]
    assert co.collect_js() == ["a.js", "b.js"]


def test_def_annotations_and_defaults(project):
    project.write({
        "a.jx": """{# def
    title: str,
    count: int = 0,
    items: list[str] = [],
    data: dict[str, int] = {"a": 1},
    flag=true,
    who=None,
#}
{{ title }} {{ count }} {{ items }} {{ data }} {{ flag }} {{ who }}
"""
    })
    project.assert_same("a.jx", title="t")
    project.assert_same("a.jx", title="t", count=3, items=["x"], flag=False, who="me")


def test_missing_required_argument_raises(project):
    project.write({"a.jx": "{# def title #}{{ title }}"})
    with pytest.raises(TypeError):
        project.render_mini("a.jx")


def test_strict_missing_global_raises(project):
    project.write({"a.jx": "{{ nope }}"})
    with pytest.raises(KeyError):
        project.render_mini("a.jx")


def test_unknown_attr_raises(project):
    project.write({"a.jx": "{# def d #}{{ d.nope }}"})
    with pytest.raises(AttributeError):
        project.render_mini("a.jx", d={})


# Header declarations: `{# def #}`, `{# import #}`, `{# css #}`, `{# js #}`,
# read the way Jx reads them.


def test_header_with_markers_comments_and_plain_comments(project):
    project.write({
        "b.jx": "{#def x #}b={{ x }}",
        "a.jx": """{# A plain comment does not end the header. #}
{#- import "b.jx" as B -#}
{# def
    title,        # the page title
    tags=["#a"],  # a `#` inside quotes is kept
#}
{# def #}
{# defx not a declaration #}
<h1>{{ title }}</h1><B x={{ tags[0] }} />
""",
    })
    project.assert_same("a.jx", title="T")


def test_inline_comments_in_asset_declarations(project):
    project.write({
        "a.jx": '{# css "a.css#frag",  # a fragment is not a comment\n  b.css #}{# js "a.js" # trailing #}a',
    })
    project.render_mini("a.jx")
    from proper.views import Catalog

    co = Catalog(project.mini).get_component("a.jx")
    assert co.collect_css() == ["a.css#frag", "b.css"]
    assert co.collect_js() == ["a.js"]


def test_declaration_after_the_header_is_a_plain_comment(project):
    project.write({
        "b.jx": "b",
        "a.jx": '<p>x</p>{# import "b.jx" as B #}{# def y #}{{ 1 }}',
    })
    project.assert_same("a.jx")  # `y` is not an argument: nothing is required


def test_default_keeps_none_like_jinja(project):
    """`default` replaces missing values, not `None`, unless `boolean=True`."""
    project.write({
        "a.jx": """{# def x=None, d={}, e="" #}
local none: {{ x | default("D") }}
local none, boolean: {{ x | default("D", true) }}
global none: {{ g | default("D") }}
missing global: {{ nope | default("D") }}
key none: {{ d.k | default("D") }} {{ d["k"] | default("D") }}
missing key: {{ d.zz | default("D") }} {{ d["zz"] | default("D") }}
empty string: {{ e | default("D") }}|{{ e | d("D", true) }}
chained: {{ nope | default(x) | default("D") }}
"""
    })
    html = project.assert_same("a.jx", globals={"g": None}, d={"k": None})
    assert "local none: None" in html
    assert "local none, boolean: D" in html
    assert "global none: None" in html
    assert "missing global: D" in html
    assert "key none: None None" in html
    assert "missing key: D D" in html
    assert "empty string: |D" in html
    assert "chained: None" in html


# Generated-code paths: plain keyword arguments and fused f-strings


def test_component_attribute_names(project):
    """Plain kwargs where Python allows them, a dict for the rest, same result."""
    project.write({
        "c.jx": '{# def a="-", b="-" #}<i {{ attrs.render() }}>{{ a }}{{ b }}|{{ content }}</i>',
        "page.jx": """{# import "c.jx" as C #}
<C a="1" b={{ 2 }} data-id="x" class="k" for="f" if="i" @click="go" x:y="z" hidden />
<C content="given" />
<C a="x">inner</C>
""",
    })
    project.assert_same("page.jx")


def test_text_and_expressions_in_one_fstring(project):
    project.write({
        "page.jx": """{# def s, d #}<p a='1' b="2">{ } {{ "{" }}{{ '}' }} \\n \\\\ \\' </p>
<b>{{ s }}{{ s ~ '!' }}{{ d["k"] }}{{ {"a": 1}["a"] }}{{ 1 != 2 }}{{ "it's" }}{{ 'say "hi"' }}</b>
\tñ → ✓ {{ s | upper }}{% raw %}{{ raw }} {% if %}{% endraw %}{{ s }}
""",
    })
    project.assert_same("page.jx", s="x{y}z", d={"k": "v"})
