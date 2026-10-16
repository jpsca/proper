"""
Autoescape: `{{ }}` escapes what it renders, as Jinja and Jx do with
autoescape on, in the components whose extension is in the catalog's list.
"""

import subprocess

import pytest
from markupsafe import Markup

from proper.views import Catalog, ComponentNotCompiledError
from proper.views.attrs import Attrs
from proper.views.catalog import normalize_autoescape
from proper.views.runtime import escape_output, mconcat
from .helpers import BIN, Project, load_module, run_minijx


M = Markup("<i>m</i>")


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


@pytest.fixture
def escaped(tmp_path, expected) -> Project:
    return Project(tmp_path, expected, autoescape=True)


# The same output as Jinja / Jx with autoescape


@pytest.mark.parametrize("source, kwargs", [
    ('{{ "<b>" }}', {}),
    ("{{ 1 < 2 }}{{ 3 }}{{ none }}{{ true }}", {}),
    ('{{ x ~ "<b>" }}', {"x": "<a>"}),
    ('{{ m ~ "<b>" ~ 1 }}', {"m": M}),
    ('{% set y = x ~ "!" %}{{ y }}', {"x": "<a>"}),
    ('{{ x if x else "<none>" }}', {"x": ""}),
    ('{{ x | default("<d>") }}', {"x": None}),
    ("{% filter upper %}<b>{{ x }}</b>{% endfilter %}", {"x": "<a>"}),
    ('{{ [x, "y"] | join(", ") }}', {"x": "<a>"}),
    ('{{ [m, x] | join("<br>") }}', {"x": "<a>", "m": M}),
    ("{{ [m, x] | join(sep) }}", {"x": "<a>", "m": M, "sep": Markup("<br>")}),
    ('{{ "%s!" | format(x) }}', {"x": "<a>"}),
    ("{{ m | format(x) }}", {"x": "<a>", "m": Markup("<p>%s</p>")}),
    ('{{ m | replace("m", x) }}', {"x": "<a>", "m": M}),
    ('{{ x | replace("a", m) }}', {"x": "<a>", "m": M}),
    ('{{ x | replace("a", "<b>") }}', {"x": "<a>"}),
    ("{{ m | upper }}{{ m | lower }}{{ m | capitalize }}{{ m | trim }}{{ m | center(12) }}", {"m": M}),
    ("{{ m | string }}{{ x | string }}", {"m": M, "x": "<a>"}),
    ("{{ m | title }}", {"m": M}),
    ('{{ m | truncate(3, end="") }}', {"m": M}),
    ("{{ x | e | e }}{{ x | escape }}{{ m | e }}", {"x": "<a>", "m": M}),
    ("{{ m | forceescape }}", {"m": M}),
    ("{{ x | safe }}{{ 3 | safe }}", {"x": "<a>"}),
    ("{{ x | striptags }}", {"x": "<b>a &amp; b</b>"}),
    ('{{ {"k": x} | tojson }}', {"x": "<a>'&"}),
    ("{{ x | indent(2) }}|{{ m | indent(2) }}", {"x": "a\n<b>", "m": Markup("a\n<b>")}),
    ("{{ x | wordwrap(3) }}", {"x": "<a> <b> <c>"}),
    ("{{ xs | map('upper') | join(',') }}", {"xs": ["<a>", "b"]}),
    ("{{ m }}{{ x }}{{ 1.5 }}{{ n }}", {"m": M, "x": "'\"&<>", "n": None}),
    ("{% for i in xs %}{{ loop.index }}{{ i }}{% endfor %}", {"xs": ["<a>", "&"]}),
])
def test_same_as_jinja(escaped, source, kwargs):
    names = ", ".join(sorted(kwargs))
    header = f"{{# def {names} #}}" if names else ""
    escaped.write({"a.jx": header + source})
    escaped.assert_same("a.jx", **kwargs)


def test_components_content_and_attrs_same_as_jx(escaped):
    escaped.write({
        "child.jx": "{# def title #}<h1 {{ attrs.render() }}>{{ title }}</h1>{{ content }}",
        "page.jx": (
            '{# import "child.jx" as Child #}{# def v #}'
            '<Child title="a & <b>" data-x="1 & 2" data-y={{ v }}>x & <y> {{ v }}</Child>'
        ),
    })
    escaped.assert_same("page.jx", v="<v>")
    escaped.assert_same("child.jx", title="t", content="<c>")
    escaped.assert_same("child.jx", title="t", content=Markup("<c>"))


def test_slots_and_recursive_loops_same_as_jx(escaped):
    escaped.write({
        "box.jx": "<div>{% slot head %}<i>{{ '<default>' }}</i>{% endslot %}{{ content }}</div>",
        "page.jx": """{# import "box.jx" as Box #}{# def tree, v #}
<Box>{% fill head %}<b>{{ v }}</b>{% endfill %}{{ v }}</Box>
<ul>{% for n in tree recursive %}<li>{{ n.k }}{% if n.c %}<ul>{{ loop(n.c) }}</ul>{% endif %}</li>{% endfor %}</ul>""",
    })
    tree = [{"k": "<r>", "c": [{"k": "<c>", "c": []}]}]
    escaped.assert_same("page.jx", tree=tree, v="<v>")


@pytest.mark.parametrize("value", [
    "a & b < c",
    Markup("a &amp; <b>"),
    'say "hi"',
    """both ' and " """,
])
def test_attrs_values_same_as_jx(project, value):
    """In both modes, as Jx: `&` and `<` escaped unless the value is markup."""
    project.write({
        "child.jx": "<p {{ attrs.render() }}></p>",
        "page.jx": '{# import "child.jx" as Child #}{# def v #}<Child title={{ v }} />',
    })
    project.assert_same("page.jx", v=value)


# Which components are compiled with autoescape


def test_extension_decides(tmp_path):
    write(tmp_path, {
        "card.jx": "{# def s #}{{ s }}",
        "page.html.jx": "{# def s #}{{ s }}",
        "feed.xml.jx": "{# def s #}{{ s }}",
        "mail.txt.jx": "{# def s #}{{ s }}",
        "data.JSON.jx": "{# def s #}{{ s }}",
    })
    catalog = Catalog(tmp_path)
    assert catalog.autoescape == ("html", "jx", "xml")
    for name in ("card.jx", "page.html.jx", "feed.xml.jx"):
        html = catalog.render(name, s="<a>")
        assert html == "&lt;a&gt;"
        assert isinstance(html, Markup)
    for name in ("mail.txt.jx", "data.JSON.jx"):
        text = catalog.render(name, s="<a>")
        assert text == "<a>"
        assert type(text) is str


def test_custom_extensions(tmp_path):
    write(tmp_path, {"card.jx": "{# def s #}{{ s }}", "mail.txt.jx": "{# def s #}{{ s }}"})
    catalog = Catalog(tmp_path, autoescape=[".TXT"])
    assert catalog.autoescape == ("txt",)
    assert catalog.render("card.jx", s="<a>") == "<a>"
    assert catalog.render("mail.txt.jx", s="<a>") == "&lt;a&gt;"


def test_autoescape_off(tmp_path):
    write(tmp_path, {"card.jx": "{# def s #}{{ s }}"})
    catalog = Catalog(tmp_path, autoescape=False)
    assert catalog.autoescape == ()
    html = catalog.render("card.jx", s="<a>")
    assert html == "<a>"
    assert type(html) is str


def test_text_page_with_an_html_layout(tmp_path):
    """Each component keeps its own mode when it is copied into another
    module. The content is the template author's, so an escaped layout does
    not escape it, even from a page without autoescape; its arguments are
    data, and are escaped."""
    write(tmp_path, {
        "layout.jx": "{# def title #}<h1>{{ title }}</h1>{{ content }}",
        "mail.txt.jx": '{# import "layout.jx" as Layout #}{# def s #}<Layout title={{ s }}><p>{{ s }} & co</p></Layout>',
    })
    catalog = Catalog(tmp_path)
    text = catalog.render("mail.txt.jx", s="<a>")
    assert text == "<h1>&lt;a&gt;</h1><p><a> & co</p>"
    assert type(text) is str


def test_html_page_with_a_text_component(tmp_path):
    """The other way around: the content of a component without autoescape
    is rendered as it is, and so is its output in the escaped page."""
    write(tmp_path, {
        "plain.txt.jx": "{# def title #}[{{ title }}] {{ content }}",
        "page.jx": '{# import "plain.txt.jx" as Plain #}{# def s #}<Plain title={{ s }}><b>{{ s }}</b></Plain>',
    })
    html = Catalog(tmp_path).render("page.jx", s="<a>")
    assert html == "[<a>] <b>&lt;a&gt;</b>"
    assert isinstance(html, Markup)


def test_content_is_plain_for_a_component_without_autoescape(tmp_path):
    write(tmp_path, {
        "plain.txt.jx": "{{ content }}",
        "page.jx": '{# import "plain.txt.jx" as Plain #}<Plain>x</Plain>',
    })
    assert run_minijx("--autoescape=", tmp_path).returncode == 0
    assert "_M(" not in (tmp_path / "page.py").read_text()


def test_module_declares_its_mode(tmp_path):
    write(tmp_path, {"card.jx": "x", "mail.txt.jx": "x"})
    assert run_minijx(tmp_path).returncode == 0
    card = load_module(tmp_path / "card.py")
    mail = load_module(tmp_path / "mail_txt.py")
    assert card.AUTOESCAPE == mail.AUTOESCAPE == ("html", "jx", "xml")
    assert card.ESCAPED is True
    assert mail.ESCAPED is False


def test_cli_extensions_are_normalized(tmp_path):
    write(tmp_path, {"card.jx": "x"})
    assert run_minijx("--autoescape= .TXT,html,,txt", tmp_path).returncode == 0
    assert load_module(tmp_path / "card.py").AUTOESCAPE == ("html", "txt")


def test_cli_rejects_a_bad_extension(tmp_path):
    result = subprocess.run([str(BIN), "--autoescape=h/tml", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "invalid extension for --autoescape: h/tml" in result.stderr


def test_cli_needs_a_folder():
    result = subprocess.run([str(BIN), "--autoescape=html"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "no folders given" in result.stderr


# The catalog


def test_module_compiled_with_other_extensions_is_recompiled(tmp_path):
    write(tmp_path, {"card.jx": "{# def s #}{{ s }}"})
    assert run_minijx("--autoescape=", tmp_path).returncode == 0
    catalog = Catalog(tmp_path, compiler=BIN)
    assert catalog.render("card.jx", s="<a>") == "&lt;a&gt;"


def test_module_compiled_with_other_extensions_without_compiler(tmp_path):
    write(tmp_path, {"card.jx": "{# def s #}{{ s }}"})
    assert run_minijx("--autoescape=", tmp_path).returncode == 0
    catalog = Catalog(tmp_path, compiler=False, auto_reload=False)
    with pytest.raises(ComponentNotCompiledError, match="compiled with autoescape for \\(\\)"):
        catalog.render("card.jx", s="<a>")
    catalog = Catalog(tmp_path, compiler=False, auto_reload=True)
    with pytest.raises(ComponentNotCompiledError, match="compiled with autoescape for \\(\\)"):
        catalog.render("card.jx", s="<a>")


@pytest.mark.parametrize("name", ["e", "escape", "forceescape", "safe"])
def test_trusted_filters_cannot_be_replaced(tmp_path, name):
    with pytest.raises(ValueError, match=f"Cannot replace the filter\\(s\\) '{name}'"):
        Catalog(tmp_path, filters={name: str})
    Catalog(tmp_path, filters={name: str}, autoescape=False)


def test_custom_filters_get_the_autoescape_join(tmp_path):
    write(tmp_path, {
        "card.jx": "{# def m, s #}{{ [m, s] | join(', ') }}|{{ s | shout }}",
        "mail.txt.jx": "{# def m, s #}{{ [m, s] | join(', ') }}",
    })
    catalog = Catalog(tmp_path, filters={"shout": lambda s: s.upper() + "!"})
    assert catalog.render("card.jx", m=M, s="<a>") == "<i>m</i>, &lt;a&gt;|&lt;A&gt;!"
    assert catalog.render("mail.txt.jx", m=M, s="<a>") == "<i>m</i>, <a>"


def test_assets_helpers_are_markup(tmp_path):
    write(tmp_path, {"card.jx": '{# css "a.css" #}{# js "a.js" #}{{ assets.render() }}'})
    html = Catalog(tmp_path).render("card.jx")
    assert html == '<link rel="stylesheet" href="a.css">\n<script type="module" src="a.js"></script>'


@pytest.mark.parametrize("value, expected", [
    (True, ("html", "jx", "xml")),
    (False, ()),
    (None, ()),
    ("xml, .HTML", ("html", "xml")),
    (["txt", "txt", ""], ("txt",)),
])
def test_normalize_autoescape(value, expected):
    assert normalize_autoescape(value) == expected


def test_normalize_autoescape_rejects_a_bad_extension():
    with pytest.raises(ValueError, match="Invalid extension"):
        normalize_autoescape(["h/tml"])


# Runtime


class Html:
    def __html__(self):
        return "<b>html</b>"


@pytest.mark.parametrize("value, expected", [
    ("<a href='x'>&\"", "&lt;a href=&#39;x&#39;&gt;&amp;&#34;"),
    ("plain", "plain"),
    (42, "42"),
    (1.5, "1.5"),
    (None, "None"),
    (True, "True"),
    (M, "<i>m</i>"),
    (Html(), "<b>html</b>"),
    (["<a>"], "[&#39;&lt;a&gt;&#39;]"),
])
def test_escape_output(value, expected):
    result = escape_output(value)
    assert result == expected
    assert isinstance(result, str)


def test_escape_output_uses_markupsafes_fast_loop():
    from proper.views import runtime

    assert runtime._escape_inner.__module__ in ("markupsafe._speedups", "markupsafe._native")


def test_mconcat():
    assert mconcat("<a>", 1) == "<a>1"
    assert type(mconcat("<a>", 1)) is str
    assert mconcat(M, "<a>", 1) == Markup("<i>m</i>&lt;a&gt;1")


def test_attrs_render_is_markup():
    assert isinstance(Attrs({"a": "1"}).render(), Markup)
    assert isinstance(Attrs({}).render(), Markup)
    assert isinstance(Attrs({"hidden": True}).render(), Markup)
    assert Attrs({"hidden": True, "a": "x&y"}).render() == 'a="x&amp;y" hidden'
