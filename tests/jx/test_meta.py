"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from pathlib import Path

import pytest

from proper.jx.meta import (
    DuplicateDefDeclaration,
    InvalidArgument,
    InvalidImport,
    PathTraversalError,
    extract_metadata,
)


def test_empty_source():
    """Test that empty source returns empty metadata."""
    source = ""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")
    assert meta.required == {}
    assert meta.optional == {}
    assert meta.imports == {}
    assert meta.css == ()
    assert meta.js == ()


def test_source_without_metadata():
    """Test that source without metadata comments returns empty metadata."""
    source = """<div>Hello world</div>"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {}
    assert meta.optional == {}
    assert meta.imports == {}
    assert meta.css == ()
    assert meta.js == ()


def test_def_metadata():
    """Test extraction of required and optional arguments."""
    source = """
{# def
    name,
    age=18,
    is_active=true
#}
<div>Hello {{ name }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {"name": None}
    assert meta.optional == {"age": (18, None), "is_active": (True, None)}


def test_def_with_type_annotations():
    """Test extraction of arguments with type annotations."""
    source = """
{# def
    title: str,
    count: int = 0,
    items: list[str] = [],
    data: dict[str, int] = {}
#}
<div>{{ title }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {"title": str}
    assert meta.optional == {
        "count": (0, int),
        "items": ([], list),
        "data": ({}, dict),
    }


def test_unknown_types():
    source = """
{# def
    name: Any,
    items: list[Whatever] = []
#}
<div>Hello {{ name }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {"name": None}
    assert meta.optional == {"items": ([], list)}


def test_unsupported_type_annotations():
    """Test that unsupported type annotations (union types, qualified names) return None."""
    source = """
{# def
    value: int | str,
    data: typing.List = []
#}
<div>{{ value }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    # Union types (ast.BinOp) and qualified names (ast.Attribute) are not supported
    # and should return None for the type
    assert meta.required == {"value": None}
    assert meta.optional == {"data": ([], None)}



def test_def_with_allowed_expressions():
    """Test extraction of arguments with allowed expressions."""
    source = """
{# def
    max_items=max(10, 20),
    min_value=min(5, 10),
    total=sum([1, 2, 3]),
    length=len("hello"),
    power=pow(2, 3)
#}
<div>Config</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.optional == {
        "max_items": (20, None),
        "min_value": (5, None),
        "total": (6, None),
        "length": (5, None),
        "power": (8, None),
    }

def test_invalid_argument():
    """Test that invalid arguments raise an exception."""
    source = """
{# def name=invalid_function() #}
<div>Hello {{ name }}</div>
"""
    with pytest.raises(InvalidArgument):
        base = Path("dummy")
        extract_metadata(source, base, base / "test.jx")


def test_unparsable_argument():
    """Test that unparseable arguments raise an exception."""
    source = """
{# def name=$3 #}
<div>Hello {{ name }}</div>
"""
    with pytest.raises(InvalidArgument):
        base = Path("dummy")
        extract_metadata(source, base, base / "test.jx")


def test_invalid_expression():
    """Test that invalid expressions raise an exception."""
    source = """
{# def name=5/0 #}
<div>Hello {{ name }}</div>
"""
    with pytest.raises(ZeroDivisionError):
        base = Path("dummy")
        extract_metadata(source, base, base / "test.jx")


def test_import_metadata():
    """Test extraction of imports."""
    source = """
{# import "components/button.jx" as Button #}
{# import "components/header.jx" as Header #}
<div>{{ Button() }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.imports == {
        "Button": "components/button.jx",
        "Header": "components/header.jx"
    }


def test_relative_import_metadata():
    """Test extraction of relative imports."""
    base = Path("/app/views")
    source = """
{# import "./button.jx" as Button #}
<div>{{ Button() }}</div>
    """
    meta = extract_metadata(source, base, base / "foo/bar.jx")

    assert meta.imports == {
        "Button": "foo/button.jx",
    }


def test_complex_relative_import_metadata():
    """Test extraction of complex relative imports."""
    base = Path.cwd() / "views"
    source = """
{# import "../forms/button.jx" as Button #}
<div>{{ Button() }}</div>
    """
    meta = extract_metadata(source, base, base / "foo/bar/header.jx")

    assert meta.imports == {
        "Button": "foo/forms/button.jx",
    }

def test_invalid_relative_import():
    """Test that invalid relative imports raise an exception."""
    base = Path("/app/views")
    source = """
{# import ../button.jx as Button #}
<div>{{ Button() }}</div>
"""
    with pytest.raises(InvalidImport):
        extract_metadata(source, base, base / "test.jx")


def test_path_traversal_attack():
    """Test that path traversal attempts are blocked."""
    base = Path("/app/views")
    source = """
{# import "../../../etc/passwd" as Secret #}
<div>{{ Secret() }}</div>
"""
    with pytest.raises(PathTraversalError) as exc_info:
        extract_metadata(source, base, base / "test.jx")
    assert "escapes component root" in str(exc_info.value)


def test_path_traversal_from_nested_component():
    """Test that path traversal is blocked even from deeply nested components."""
    base = Path("/app/views")
    source = """
{# import "../../../../etc/passwd" as Secret #}
<div>{{ Secret() }}</div>
"""
    # Paths starting with ".." are also relative and validated
    with pytest.raises(PathTraversalError) as exc_info:
        extract_metadata(source, base, base / "deep/nested/component.jx")
    assert "escapes component root" in str(exc_info.value)


def test_path_traversal_with_dot_prefix():
    """Test that path traversal with dot prefix is blocked."""
    base = Path("/app/views")
    source = """
{# import "./../../../etc/passwd" as Secret #}
<div>{{ Secret() }}</div>
"""
    with pytest.raises(PathTraversalError) as exc_info:
        extract_metadata(source, base, base / "test.jx")
    assert "escapes component root" in str(exc_info.value)


def test_css_metadata():
    """Test extraction of CSS references."""
    source = """
{# css "/static/styles.css", "https://cdn.example.com/style.css" #}
<div>Styled content</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.css == (
        "/static/styles.css",
        "https://cdn.example.com/style.css"
    )


def test_js_metadata():
    """Test extraction of JS references."""
    source = """
{# js "/static/script.js", "https://cdn.example.com/script.js" #}
<div>Interactive content</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.js == (
        "/static/script.js",
        "https://cdn.example.com/script.js"
    )


def test_css_commas():
    """Test extraction of CSS references even with extra commas."""
    source = """
{# css "/static/styles.css",, "https://cdn.example.com/style.css", #}
<div>Styled content</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.css == (
        "/static/styles.css",
        "https://cdn.example.com/style.css",
    )


def test_js_commas():
    """Test extraction of JS references even with extra commas."""
    source = """
{# js "/static/script.js",, "https://cdn.example.com/script.js", #}
<div>Interactive content</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.js == (
        "/static/script.js",
        "https://cdn.example.com/script.js",
    )


def test_comments_in_metadata():
    """Test that comments in metadata are ignored."""
    source = """
{# def
  name, # This is a required field
  age=18 # Default age
#}
<div>Hello {{ name }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {"name": None}
    assert meta.optional == {"age": (18, None)}


def test_multiple_metadata_blocks():
    """Test extracting multiple metadata blocks."""
    source = """
{# def name, age=21 #}
{# import "button.jx" as Button #}
{# css "/style.css" #}
{# js "/script.js" #}
<div>Hello {{ name }}</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")

    assert meta.required == {"name": None}
    assert meta.optional == {"age": (21, None)}
    assert meta.imports == {"Button": "button.jx"}
    assert meta.css == ("/style.css", )
    assert meta.js == ("/script.js", )


def test_duplicate_def_declaration():
    """Test that duplicate def declarations raise an exception."""
    source = """
{# def name #}
{# def age #}
<div>Hello {{ name }}</div>
"""
    with pytest.raises(DuplicateDefDeclaration):
        base = Path("dummy")
        extract_metadata(source, base, base / "test.jx")


def test_empty_meta_declarations():
    """Test that empty meta declarations are handled correctly."""
    source = """
{# def #}
<div>Hello world</div>
"""
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")
    assert meta.required == {}
    assert meta.optional == {}
    assert meta.imports == {}


def test_hash_in_css_url_preserved():
    """URLs with # fragments in CSS declarations should not be corrupted."""
    source = '{#css "/style.css#v2", "/other.css" #}\n<div>test</div>'
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")
    assert meta.css == ("/style.css#v2", "/other.css")


def test_hash_in_js_url_preserved():
    """URLs with # fragments in JS declarations should not be corrupted."""
    source = '{#js "/script.js#module" #}\n<div>test</div>'
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")
    assert meta.js == ("/script.js#module",)


def test_inline_comment_with_quoted_hash():
    """Inline comments should still work alongside quoted URLs with #."""
    source = '{#css "/style.css#v2" # load versioned styles\n#}\n<div />'
    base = Path("dummy")
    meta = extract_metadata(source, base, base / "test.jx")
    assert meta.css == ("/style.css#v2",)


def test_relative_import_in_string_template():
    """Relative imports should raise InvalidImport when fullpath is empty (string templates)."""
    source = '{#import "./button.jx" as Button #}\n<Button />'
    with pytest.raises(InvalidImport, match="Relative import"):
        extract_metadata(source, base_path=Path(), fullpath=Path())
