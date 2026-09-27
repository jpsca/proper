"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from proper.jx import Catalog
from proper.jx.cli import _is_file_path, load_catalog, main


def test_load_catalog_invalid_format(capsys):
    """Test load_catalog with invalid format (no colon)."""
    with pytest.raises(SystemExit) as exc_info:
        load_catalog("no_colon_here")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Invalid catalog path" in captured.out


def test_load_catalog_missing_module(capsys):
    """Test load_catalog with a module that doesn't exist."""
    with pytest.raises(SystemExit) as exc_info:
        load_catalog("nonexistent.module:catalog")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Could not import module" in captured.out


def test_load_catalog_missing_attribute(capsys):
    """Test load_catalog with a missing attribute."""
    with pytest.raises(SystemExit) as exc_info:
        load_catalog("proper.jx:nonexistent_attr")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Could not resolve" in captured.out


def test_load_catalog_missing_nested_attribute(capsys):
    """Test load_catalog with a missing nested attribute."""
    with pytest.raises(SystemExit) as exc_info:
        load_catalog("proper.jx:Catalog.nonexistent")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Could not resolve" in captured.out


def test_load_catalog_success():
    """Test load_catalog successfully imports a catalog."""
    catalog = load_catalog("proper.jx:Catalog")
    assert catalog is Catalog


def test_load_catalog_dotted_attribute():
    """Test load_catalog with a dotted attribute path."""
    # jx.Catalog.__name__ is "Catalog" (a string)
    result = load_catalog("proper.jx:Catalog.__name__")
    assert result == "Catalog"


# -- File path detection --


def test_is_file_path_with_slash():
    assert _is_file_path("docs/docs.py") is True


def test_is_file_path_with_py_extension():
    assert _is_file_path("setup.py") is True


def test_is_file_path_with_module_path():
    assert _is_file_path("myapp.setup") is False


# -- load_catalog from file path --


def test_load_catalog_file_path(tmp_path):
    """Test load_catalog with a file path instead of module path."""
    setup_file = tmp_path / "mysetup.py"
    setup_file.write_text(
        "from proper.jx import Catalog\n"
        "catalog = Catalog()\n"
    )
    result = load_catalog(f"{setup_file}:catalog")
    assert isinstance(result, Catalog)


def test_load_catalog_file_path_nested_attr(tmp_path):
    """Test load_catalog with a file path and dotted attribute."""
    setup_file = tmp_path / "mysetup.py"
    setup_file.write_text(
        "from proper.jx import Catalog\n"
        "class docs:\n"
        "    catalog = Catalog()\n"
    )
    result = load_catalog(f"{setup_file}:docs.catalog")
    assert isinstance(result, Catalog)


def test_load_catalog_file_path_not_found(capsys):
    """Test load_catalog with a file path that doesn't exist."""
    with pytest.raises(SystemExit) as exc_info:
        load_catalog("nonexistent/file.py:catalog")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "File not found" in captured.out


def test_load_catalog_file_path_missing_attr(tmp_path, capsys):
    """Test load_catalog with a file path but missing attribute."""
    setup_file = tmp_path / "mysetup.py"
    setup_file.write_text("x = 1\n")
    with pytest.raises(SystemExit) as exc_info:
        load_catalog(f"{setup_file}:catalog")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Could not resolve" in captured.out


def test_main_check_file_path(tmp_path, capsys):
    """Test main check subcommand with a file path argument."""
    folder = tmp_path / "components"
    folder.mkdir()
    (folder / "alert.jx").write_text("<div>Alert</div>")

    setup_file = tmp_path / "mysetup.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog('{folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "check", f"{setup_file}:catalog"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "alert.jx - OK" in captured.out


def test_main_no_command(capsys):
    """Test main with no subcommand prints help and exits."""
    with patch.object(sys, "argv", ["jx"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_check(tmp_path, capsys):
    """Test main with check subcommand."""
    # Create a valid component
    folder = tmp_path / "components"
    folder.mkdir()
    (folder / "button.jx").write_text("<button>Click</button>")

    # Create a module that exposes a catalog
    setup_file = tmp_path / "testsetup.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog('{folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "check", "testsetup:catalog"]):
        sys.path.insert(0, str(tmp_path))
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            sys.path.pop(0)
            sys.modules.pop("testsetup", None)

    captured = capsys.readouterr()
    assert "button.jx - OK" in captured.out


def test_main_check_json(tmp_path, capsys):
    """Test main with check --format json."""
    folder = tmp_path / "components"
    folder.mkdir()
    (folder / "card.jx").write_text("<div>OK</div>")

    setup_file = tmp_path / "testsetup2.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog('{folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "check", "--format", "json", "testsetup2:catalog"]):
        sys.path.insert(0, str(tmp_path))
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            sys.path.pop(0)
            sys.modules.pop("testsetup2", None)

    import json

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["checked"] == 1
    assert result["errors"] == []


def test_main_collect_assets(tmp_path, capsys):
    """Test main with collect_assets subcommand."""
    # Create component and asset folders
    comp_folder = tmp_path / "components"
    comp_folder.mkdir()
    (comp_folder / "widget.jx").write_text("<div>widget</div>")

    assets_folder = tmp_path / "assets"
    assets_folder.mkdir()
    (assets_folder / "style.css").write_text("body { color: red; }")

    output_folder = tmp_path / "static"

    setup_file = tmp_path / "testsetup3.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog()\n"
        f"catalog.add_folder('{comp_folder}', prefix='ui', assets='{assets_folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "collect_assets", "testsetup3:catalog", str(output_folder)]):
        sys.path.insert(0, str(tmp_path))
        try:
            main()
        finally:
            sys.path.pop(0)
            sys.modules.pop("testsetup3", None)

    captured = capsys.readouterr()
    assert "ui/style.css" in captured.out
    assert "1 file collected" in captured.out
    assert (output_folder / "ui" / "style.css").exists()


def test_main_collect_assets_multiple(tmp_path, capsys):
    """Test collect_assets with multiple files uses plural."""
    comp_folder = tmp_path / "components"
    comp_folder.mkdir()
    (comp_folder / "a.jx").write_text("<div>a</div>")

    assets_folder = tmp_path / "assets"
    assets_folder.mkdir()
    (assets_folder / "a.css").write_text(".a {}")
    (assets_folder / "b.css").write_text(".b {}")

    output_folder = tmp_path / "static"

    setup_file = tmp_path / "testsetup4.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog()\n"
        f"catalog.add_folder('{comp_folder}', prefix='ui', assets='{assets_folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "collect_assets", "testsetup4:catalog", str(output_folder)]):
        sys.path.insert(0, str(tmp_path))
        try:
            main()
        finally:
            sys.path.pop(0)
            sys.modules.pop("testsetup4", None)

    captured = capsys.readouterr()
    assert "2 files collected" in captured.out


def test_load_module_from_file_bad_spec(tmp_path, capsys):
    """Test _load_module_from_file with an unloadable file."""
    bad_file = tmp_path / "not_python.txt"
    bad_file.write_text("not a python file")
    from proper.jx.cli import _load_module_from_file

    with pytest.raises(SystemExit) as exc_info:
        _load_module_from_file(str(bad_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Cannot load module" in captured.out


def test_main_collect_assets_no_prefix(tmp_path, capsys):
    """Test collect_assets with no assets folders produces 0 files."""
    comp_folder = tmp_path / "components"
    comp_folder.mkdir()
    (comp_folder / "btn.jx").write_text("<button />")

    output_folder = tmp_path / "static"

    setup_file = tmp_path / "testsetup5.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog()\n"
        f"catalog.add_folder('{comp_folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "collect_assets", "testsetup5:catalog", str(output_folder)]):
        sys.path.insert(0, str(tmp_path))
        try:
            main()
        finally:
            sys.path.pop(0)
            sys.modules.pop("testsetup5", None)

    captured = capsys.readouterr()
    assert "0 files collected" in captured.out


# -- info --


def test_main_info_json(tmp_path, capsys):
    """`info` reports the catalog's folders and file extension as JSON."""
    folder = tmp_path / "components"
    folder.mkdir()
    (folder / "btn.jx").write_text("<button />")
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "modal.jx").write_text("<div />")

    setup_file = tmp_path / "infosetup.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\n"
        f"catalog = Catalog('{folder}')\n"
        f"catalog.add_folder('{ui}', prefix='ui')\n"
    )

    with patch.object(sys, "argv", ["jx", "info", f"{setup_file}:catalog", "--format", "json"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    result = json.loads(capsys.readouterr().out)
    assert result["file_ext"] == ".jx"
    assert [f["prefix"] for f in result["folders"]] == ["", "ui"]
    assert [f["path"] for f in result["folders"]] == [str(folder), str(ui)]
    assert result["components"] == ["@ui/modal.jx", "btn.jx"]


def test_main_info_text(tmp_path, capsys):
    """`info` has a readable default format."""
    folder = tmp_path / "components"
    folder.mkdir()
    (folder / "btn.jx").write_text("<button />")

    setup_file = tmp_path / "infosetup2.py"
    setup_file.write_text(
        f"from proper.jx import Catalog\ncatalog = Catalog('{folder}')\n"
    )

    with patch.object(sys, "argv", ["jx", "info", f"{setup_file}:catalog"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    out = capsys.readouterr().out
    assert "file_ext: .jx" in out
    assert str(folder) in out


def test_main_info_no_folders(tmp_path, capsys):
    """A catalog with no registered folder says so instead of printing nothing."""
    setup_file = tmp_path / "infosetup3.py"
    setup_file.write_text("from proper.jx import Catalog\ncatalog = Catalog()\n")

    with patch.object(sys, "argv", ["jx", "info", f"{setup_file}:catalog"]):
        with pytest.raises(SystemExit):
            main()

    assert "none registered" in capsys.readouterr().out


# -- parse --


def test_main_parse_json(tmp_path, capsys):
    """`parse` reports imports and tags with offsets that map back to source."""
    source = '{#import "./button.jx" as Button #}\n<div>\n  <Button label="Hi" />\n</div>\n'
    comp = tmp_path / "page.jx"
    comp.write_text(source)

    with patch.object(sys, "argv", ["jx", "parse", str(comp)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    result = json.loads(capsys.readouterr().out)
    imp = result["imports"][0]
    assert imp["name"] == "Button"
    assert imp["path"] == "./button.jx"
    # The offsets are what an editor turns into clickable ranges.
    assert source[imp["path_start"]:imp["path_end"]] == "./button.jx"
    assert source[imp["name_start"]:imp["name_end"]] == "Button"

    tag = result["tags"][0]
    assert tag["name"] == "Button"
    assert tag["line"] == 3
    assert source[tag["start"]:tag["end"]] == '<Button label="Hi" />'


def test_main_parse_stdin(tmp_path, capsys):
    """`--stdin` parses an unsaved buffer, using the path only as a name."""
    comp = tmp_path / "unsaved.jx"  # deliberately never written to disk

    with patch.object(sys, "argv", ["jx", "parse", str(comp), "--stdin"]):
        with patch.object(sys, "stdin", StringIO('{#import "./a.jx" as A #}\n<A />\n')):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    result = json.loads(capsys.readouterr().out)
    assert result["imports"][0]["name"] == "A"
    assert [t["name"] for t in result["tags"]] == ["A"]


def test_main_parse_ignores_raw_and_comments(tmp_path, capsys):
    """A tag is only a tag where the parser says it is."""
    comp = tmp_path / "page.jx"
    comp.write_text(
        "<Real />\n"
        "{% raw %}<Fake />{% endraw %}\n"
        "{# <AlsoFake /> #}\n"
    )

    with patch.object(sys, "argv", ["jx", "parse", str(comp)]):
        with pytest.raises(SystemExit):
            main()

    result = json.loads(capsys.readouterr().out)
    assert [t["name"] for t in result["tags"]] == ["Real"]


def test_main_parse_broken_body_keeps_imports(tmp_path, capsys):
    """A file that does not parse still reports the imports in its header."""
    comp = tmp_path / "broken.jx"
    comp.write_text('{#import "./a.jx" as A #}\n<div>\n  <A>\n</div>\n')

    with patch.object(sys, "argv", ["jx", "parse", str(comp)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    result = json.loads(capsys.readouterr().out)
    assert result["imports"][0]["name"] == "A"
    assert result["tags"] == []
    assert result["errors"][0]["line"] == 3
    assert result["errors"][0]["col"] == 2


def test_main_parse_file_not_found(capsys):
    with patch.object(sys, "argv", ["jx", "parse", "nope/missing.jx"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
    assert "File not found" in capsys.readouterr().out
