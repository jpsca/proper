"""
The types in `{# def #}`: builtin types are checked on each render, as Jx
does (the base type of a generic, the default values too); other
annotations are kept in the signature, not evaluated. Defaults that are not
literals are evaluated on each render, so a list is never shared.
"""

import traceback
from pathlib import Path

import pytest

from proper.views import Catalog, InvalidPropType


DEF = "{# def label: str, n: int = 1, tags: list[str] = [], user: User = None, maybe: str | None = None #}"
BODY = "{{ label }}|{{ n }}|{{ tags | join(',') }}|{{ user }}|{{ maybe }}"


def jx_error(project, name, **kwargs):
    """The message of the `InvalidPropType` Jx raised (recorded)."""
    error = project.jx_error()
    assert error.name == "InvalidPropType", error.name
    return str(error)


@pytest.mark.parametrize("kwargs", [
    {"label": "a"},
    {"label": "a", "n": 2, "tags": ["x", "y"], "user": object, "maybe": None},
    {"label": "a", "n": True},  # a bool is an int, for isinstance
    {"label": "a", "maybe": 3},  # `str | None` is not checked
])
def test_right_types_same_as_jx(project, kwargs):
    project.write({"page.jx": DEF + BODY})
    project.assert_same("page.jx", **kwargs)


@pytest.mark.parametrize("kwargs", [
    {"label": 1},
    {"label": "a", "n": "2"},
    {"label": "a", "tags": ("x",)},
])
def test_wrong_types_same_message_as_jx(project, kwargs):
    project.write({"page.jx": DEF + BODY})
    assert project.compile().returncode == 0
    catalog = Catalog(project.mini, compiler=False, autoescape=project.autoescape)
    with pytest.raises(InvalidPropType) as info:
        catalog.render("page.jx", **kwargs)
    assert str(info.value) == jx_error(project, "page.jx", **kwargs)
    assert isinstance(info.value, TypeError)


def test_the_default_is_checked_too(project):
    """As in Jx: `x: str = None` fails when `x` is not given."""
    project.write({"page.jx": "{# def x: str = None #}{{ x }}"})
    assert project.compile().returncode == 0
    with pytest.raises(InvalidPropType) as info:
        Catalog(project.mini, compiler=False, autoescape=project.autoescape).render("page.jx")
    assert str(info.value) == jx_error(project, "page.jx") == "page.jx: `x` expected str, got NoneType"


def test_checked_between_components(project):
    project.write({
        "ui/card.jx": "{# def title: str, count: int = 0 #}<b>{{ title }} {{ count }}</b>",
        "page.jx": '{# import "ui/card.jx" as Card #}{# def v #}<Card title="t" count={{ v }} />',
    })
    project.assert_same("page.jx", v=3)
    with pytest.raises(InvalidPropType, match=r"^ui/card.jx: `count` expected int, got str$"):
        Catalog(project.mini, compiler=False, autoescape=project.autoescape).render("page.jx", v="3")


def test_mutable_defaults_are_new_on_each_render(project):
    project.write({"page.jx": "{# def tags=[], opts={'a': 1} #}{% do tags.append(1) %}{% do opts.update(b=2) %}{{ tags | length }}{{ opts | length }}"})
    assert project.compile().returncode == 0
    catalog = Catalog(project.mini, compiler=False, autoescape=project.autoescape)
    assert [catalog.render("page.jx") for _ in range(3)] == ["12"] * 3


def test_expression_defaults(project):
    project.write({"page.jx": "{# def n=len([1, 2]) + 1, s='a' 'b', f=1.5e2, neg=-1, t=true #}{{ n }} {{ s }} {{ f }} {{ neg }} {{ t }}"})
    project.assert_same("page.jx")


def test_annotations_that_are_not_builtin_are_not_evaluated(tmp_path):
    (tmp_path / "page.jx").write_text("{# def user: User, items: 'list[Item]' = [] #}{{ user }}")
    catalog = Catalog(tmp_path)
    assert catalog.render("page.jx", user="u") == "u"
    render = catalog.get_component("page.jx").module.render
    assert render.__annotations__["user"] == "User"


def test_the_error_points_to_the_def_line(tmp_path):
    (tmp_path / "card.jx").write_text("<b>\n{# def title: str #}{{ title }}</b>".split("\n", 1)[1])
    (tmp_path / "page.jx").write_text('{# import "card.jx" as Card #}{# def n #}\n<Card title={{ n }} />')
    with pytest.raises(InvalidPropType) as info:
        Catalog(tmp_path).render("page.jx", n=1)
    tb = [(Path(f.filename).name, f.lineno) for f in traceback.extract_tb(info.value.__traceback__)]
    assert tb[-2:] == [("page.jx", 2), ("card.jx", 1)]


# Checked when compiling: what a component call shows in the template


def compile_error(tmp_path, page, card="{# def title: str, count: int = 0, tags: list = [], on: bool = False #}x"):
    from proper.views import CompileError

    (tmp_path / "card.jx").write_text(card)
    (tmp_path / "page.jx").write_text('{# import "card.jx" as Card #}{# def v #}' + page)
    with pytest.raises(CompileError) as info:
        Catalog(tmp_path).compile()
    return str(info.value).split("page.jx:", 1)[1]


@pytest.mark.parametrize("page, error", [
    ("<Card />", "1:42: `<Card>` needs the argument `title` (card.jx)"),
    ('<Card count="3" />', "1:42: `<Card>` needs the argument `title` (card.jx)"),
    ('<Card title="t" count="3" />', "1:58: `count` of `<Card>` expects int, got str (card.jx)"),
    ("<Card title={{ 3 }} />", "1:48: `title` of `<Card>` expects str, got int (card.jx)"),
    ('<Card title="t" count={{ 1.5 }} />', "`count` of `<Card>` expects int, got float"),
    ('<Card title="t" count={{ -2.0 }} />', "`count` of `<Card>` expects int, got float"),
    ('<Card title="t" tags={{ (1, 2) }} />', "`tags` of `<Card>` expects list, got tuple"),
    ('<Card title="t" tags={{ {"a": 1} }} />', "`tags` of `<Card>` expects list, got dict"),
    ("<Card title={{ none }} />", "`title` of `<Card>` expects str, got NoneType"),
    ('<Card title="t" on="yes" />', "`on` of `<Card>` expects bool, got str"),
])
def test_compile_errors(tmp_path, page, error):
    assert error in compile_error(tmp_path, page)


@pytest.mark.parametrize("page", [
    '<Card title="t" />',
    '<Card title="t" count={{ 3 }} tags={{ [1] }} on />',
    '<Card title="t" count={{ true }} />',  # a bool is an int
    "<Card title={{ v }} count={{ v }} />",  # only known when rendering
    '<Card title={{ "a" ~ v }} count={{ 1 + 1 }} />',
    "<Card attrs={{ v }} />",  # may carry `title`
    '<Card title="t" data-x={{ 3 }} />',  # not an argument: an HTML attribute
])
def test_compiles(tmp_path, page):
    (tmp_path / "card.jx").write_text("{# def title: str, count: int = 0, tags: list = [], on: bool = False #}x")
    (tmp_path / "page.jx").write_text('{# import "card.jx" as Card #}{# def v #}' + page)
    Catalog(tmp_path).compile()


def test_content_counts_as_given(tmp_path):
    (tmp_path / "box.jx").write_text("{# def content #}<div>{{ content }}</div>")
    (tmp_path / "page.jx").write_text('{# import "box.jx" as Box #}<Box>x</Box>')
    assert Catalog(tmp_path).render("page.jx") == "<div>x</div>"
    (tmp_path / "page.jx").write_text('{# import "box.jx" as Box #}<Box />')
    from proper.views import CompileError

    with pytest.raises(CompileError, match="needs the argument `content`"):
        Catalog(tmp_path).compile()


def test_dashes_in_names(tmp_path):
    (tmp_path / "card.jx").write_text("{# def data_id: int #}{{ data_id }}")
    (tmp_path / "page.jx").write_text('{# import "card.jx" as Card #}<Card data-id={{ 7 }} />')
    assert Catalog(tmp_path).render("page.jx") == "7"


def test_every_error_of_a_component_call_in_a_file(tmp_path):
    """The errors after which the code is still valid don't stop the file:
    the others are reported too, each once, and the module isn't written."""
    from proper.views import CompileError

    (tmp_path / "card.jx").write_text("{# def title: str, count: int = 0 #}x")
    (tmp_path / "page.jx").write_text(
        '{# import "card.jx" as Card #}\n'
        "<Card />\n"
        '<Card title="t" count="3" />\n'
        "<Missing />\n"
        "<Card />\n"
    )
    catalog = Catalog(tmp_path)
    with pytest.raises(CompileError) as info:
        catalog.compile()
    assert str(info.value).splitlines() == [
        f"{tmp_path}/page.jx:2:1: `<Card>` needs the argument `title` (card.jx)",
        f"{tmp_path}/page.jx:3:17: `count` of `<Card>` expects int, got str (card.jx)",
        f'{tmp_path}/page.jx:4:1: Component `Missing` is not imported; add `{{# import "..." as Missing #}}`',
        f"{tmp_path}/page.jx:5:1: `<Card>` needs the argument `title` (card.jx)",
    ]
    assert not [path for path in tmp_path.rglob("*.py") if path.stem.startswith("page")]


def test_a_component_used_twice_reports_its_errors_once_per_file(tmp_path):
    """Once for the module of the component, and once for the page that
    uses it twice."""
    from proper.views import CompileError

    (tmp_path / "card.jx").write_text("{# def title: str #}<Missing />")
    (tmp_path / "page.jx").write_text(
        '{# import "card.jx" as Card #}<Card title="a" /><Card title="b" />'
    )
    with pytest.raises(CompileError) as info:
        Catalog(tmp_path).compile()
    errors = [line for line in str(info.value).splitlines() if "/card.jx:" in line]
    assert errors == [
        f'{tmp_path}/card.jx:1:21: Component `Missing` is not imported; add `{{# import "..." as Missing #}}`',
    ] * 2


def test_deferred_errors_come_before_the_one_that_stops_the_file(tmp_path):
    from proper.views import CompileError

    (tmp_path / "card.jx").write_text("{# def title: str #}x")
    (tmp_path / "page.jx").write_text(
        '{# import "card.jx" as Card #}\n<Card />\n{{ 1 + }}\n'
    )
    with pytest.raises(CompileError) as info:
        Catalog(tmp_path).compile()
    lines = str(info.value).splitlines()
    assert lines[0] == f"{tmp_path}/page.jx:2:1: `<Card>` needs the argument `title` (card.jx)"
    assert lines[1].startswith(f"{tmp_path}/page.jx:3:")
