"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import json

from proper.jx import Catalog
from proper.jx.tools import (
    CheckError,
    check,
    check_all,
    find_component_tags,
    format_error,
    suggest_component,
    suggest_tag,
)


def test_find_component_tags():
    source = """
<div>
  <Button label="Click" />
  <Card title="Hello">
    <CloseBtn />
  </Card>
</div>
"""
    tags = find_component_tags(source)
    assert ("Button", 3) in tags
    assert ("Card", 4) in tags
    assert ("CloseBtn", 5) in tags


def test_find_component_tags_at_line_boundary():
    source = '<Card\n  title="foo">\n  content\n</Card>'
    tags = find_component_tags(source)
    assert ("Card", 1) in tags


def test_suggest_tag():
    imported = {"Button", "Card", "Layout"}
    all_components = {"button.jx", "card.jx", "layout.jx"}

    assert suggest_tag("Buttn", imported, all_components) == "Button"
    assert suggest_tag("Crad", imported, all_components) == "Card"
    assert suggest_tag("XYZ123", imported, all_components) is None


def test_check_valid_components(folder):
    (folder / "button.jx").write_text(
        "{#def label #}\n<button>{{ label }}</button>"
    )
    (folder / "card.jx").write_text(
        '{#import "button.jx" as Button #}\n<div><Button label="OK" /></div>'
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 0


def test_check_unknown_component(folder, capsys):
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text("<div><Buttn /></div>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown component 'Buttn'" in captured.out
    assert "did you mean 'Button'?" in captured.out


def test_check_unknown_import(folder, capsys):
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text(
        '{#import "buton.jx" as Button #}\n<Button />'
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown import 'buton.jx'" in captured.out
    assert "did you mean 'button.jx'?" in captured.out


def test_check_not_imported(folder, capsys):
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text("<div><Button /></div>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Component 'Button' used but not imported" in captured.out


def test_check_single_file(folder, capsys):
    """Test checking a single file instead of a folder."""
    (folder / "button.jx").write_text("{#def label #}\n<button>{{ label }}</button>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "button.jx - OK" in captured.out


def test_check_no_components(tmp_path, capsys):
    """Test checking an empty folder with no components."""
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()

    catalog = Catalog(empty_folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "No components found" in captured.out


def test_check_invalid_utf8(folder, capsys):
    """Test checking a component with invalid UTF-8 encoding."""
    (folder / "broken.jx").write_bytes(b"<div>\xff\xfe invalid</div>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "broken.jx - Not valid UTF-8" in captured.out


def test_check_invalid_metadata(folder, capsys):
    """Test checking a component with invalid metadata syntax."""
    (folder / "broken.jx").write_text("{#def $invalid #}\n<div>test</div>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "broken.jx -" in captured.out


def test_check_unknown_import_no_suggestion(folder, capsys):
    """Test unknown import with no similar component to suggest."""
    (folder / "card.jx").write_text(
        '{#import "xyzabc123.jx" as Thing #}\n<Thing />'
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown import 'xyzabc123.jx'" in captured.out
    assert "did you mean" not in captured.out


def test_check_unknown_component_no_suggestion(folder, capsys):
    """Test unknown component tag with no similar tag to suggest."""
    (folder / "card.jx").write_text("<div><Xyzabc123 /></div>")

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown component 'Xyzabc123'" in captured.out
    assert "did you mean" not in captured.out


def test_suggest_component():
    """Test component path suggestion."""
    all_components = {"button.jx", "card.jx", "layout.jx"}

    assert suggest_component("buton.jx", all_components) == "button.jx"
    assert suggest_component("xyzabc123.jx", all_components) is None


def test_check_nonexistent_path(tmp_path, capsys):
    """Test checking an empty catalog (no components)."""
    empty_folder = tmp_path / "does_not_exist"
    empty_folder.mkdir()

    catalog = Catalog(empty_folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "No components found" in captured.out


def test_check_all_valid(folder):
    """Test check_all returns no errors for valid components."""
    (folder / "button.jx").write_text(
        "{#def label #}\n<button>{{ label }}</button>"
    )
    (folder / "card.jx").write_text(
        '{#import "button.jx" as Button #}\n<div><Button label="OK" /></div>'
    )

    catalog = Catalog(folder)
    errors, checked = check_all(catalog)
    assert checked == 2
    assert errors == []


def test_check_all_with_errors(folder):
    """Test check_all returns structured errors."""
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text("<div><Buttn /></div>")

    catalog = Catalog(folder)
    errors, checked = check_all(catalog)
    assert checked == 2
    assert len(errors) == 1
    assert errors[0].file == "card.jx"
    assert errors[0].line == 1
    assert "Buttn" in errors[0].message
    assert errors[0].suggestion == "Button"


def test_check_all_single_file(folder):
    """Test check_all with a catalog containing one component."""
    (folder / "button.jx").write_text("{#def label #}\n<button>{{ label }}</button>")

    catalog = Catalog(folder)
    errors, checked = check_all(catalog)
    assert checked == 1
    assert errors == []


def test_check_all_empty(tmp_path):
    """Test check_all with no components returns zero checked."""
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()

    catalog = Catalog(empty_folder)
    errors, checked = check_all(catalog)
    assert checked == 0
    assert errors == []


def test_check_json_format_valid(folder, capsys):
    """Test JSON output format with valid components."""
    (folder / "button.jx").write_text("<button>Click</button>")

    catalog = Catalog(folder)
    exit_code = check(catalog, format="json")
    assert exit_code == 0

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["checked"] == 1
    assert result["errors"] == []


def test_check_json_format_with_errors(folder, capsys):
    """Test JSON output format with errors."""
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text("<div><Buttn /></div>")

    catalog = Catalog(folder)
    exit_code = check(catalog, format="json")
    assert exit_code == 1

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["checked"] == 2
    assert len(result["errors"]) == 1
    assert result["errors"][0]["file"] == "card.jx"
    assert result["errors"][0]["line"] == 1
    assert "Buttn" in result["errors"][0]["message"]
    assert result["errors"][0]["suggestion"] == "Button"


def test_check_json_format_no_components(tmp_path, capsys):
    """Test JSON output format with no components."""
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()

    catalog = Catalog(empty_folder)
    exit_code = check(catalog, format="json")
    assert exit_code == 0

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["checked"] == 0
    assert result["errors"] == []


def test_check_unclosed_component_tag(folder, capsys):
    """Test that an unclosed component tag is detected."""
    (folder / "footer.jx").write_text("<footer>Footer</footer>")
    (folder / "page.jx").write_text(
        '{#import "footer.jx" as Footer #}\n<Footer>\n  <p>content</p>'
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unclosed component" in captured.out
    assert "Footer" in captured.out


def test_check_ignores_tags_in_comments(folder, capsys):
    """Component tags inside Jinja comments should not trigger errors."""
    (folder / "page.jx").write_text(
        "{# TODO: use <Card /> here #}\n<div>plain html</div>"
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "page.jx - OK" in captured.out


def test_check_ignores_tags_in_raw_blocks(folder, capsys):
    """Component tags inside raw blocks should not trigger errors."""
    (folder / "page.jx").write_text(
        '{% raw %}<Card title="hello" />{% endraw %}\n<div>plain</div>'
    )

    catalog = Catalog(folder)
    exit_code = check(catalog)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "page.jx - OK" in captured.out


def test_format_error_with_line():
    """Test format_error with a line number."""
    error = CheckError(file="card.jx", line=4, message="Unknown component 'Foo'")
    assert format_error(error) == "card.jx:4 - Unknown component 'Foo'"


def test_format_error_without_line():
    """Test format_error without a line number."""
    error = CheckError(file="card.jx", line=None, message="Not valid UTF-8")
    assert format_error(error) == "card.jx - Not valid UTF-8"


def test_format_error_with_suggestion():
    """Test format_error includes suggestion."""
    error = CheckError(
        file="card.jx", line=4, message="Unknown component 'Buttn'", suggestion="Button"
    )
    assert format_error(error) == "card.jx:4 - Unknown component 'Buttn' (did you mean 'Button'?)"


def test_check_reports_syntax_error_line(folder):
    """A syntax error is reported on the line it happens, not on line 1."""
    (folder / "button.jx").write_text("<button />")
    (folder / "broken.jx").write_text(
        '{#import "button.jx" as Button #}\n'
        "<div>\n"
        '  <Button label="Hi">\n'
        "</div>\n"
    )

    errors, _checked = check_all(Catalog(folder))
    broken = [e for e in errors if e.file == "broken.jx"]
    assert len(broken) == 1
    assert broken[0].line == 3


def test_check_reports_unknown_import_line(folder):
    """An unknown import points at its own declaration."""
    (folder / "page.jx").write_text(
        '{#css "a.css" #}\n'
        '{#import "nope.jx" as Nope #}\n'
        "<div />\n"
    )

    errors, _checked = check_all(Catalog(folder))
    assert [(e.line, e.message) for e in errors] == [
        (2, "Unknown import 'nope.jx'")
    ]


def test_check_unknown_import_line_for_relative_path(folder):
    """Relative imports are resolved in Meta, so the line is keyed by alias."""
    sub = folder / "sub"
    sub.mkdir()
    (sub / "page.jx").write_text(
        "\n"
        '{#import "./nope.jx" as Nope #}\n'
        "<div />\n"
    )

    errors, _checked = check_all(Catalog(folder))
    assert [e.line for e in errors] == [2]
