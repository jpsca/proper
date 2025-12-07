import os
import re
from pathlib import Path

import isort
from hecto import (
    COLORS,
    printf,
    render_blueprint,
)


__all__ = [
    "call",
    "printf",
    "render_blueprint",
    "sort_imports_in",
    "sort_imports",
    "add_dependencies",
    "add_to_concerns",
]


PACKAGE_MANAGERS = {
    ("uv.lock", "uv add"),
    ("poetry.lock", "poetry add"),
}


def call(cmd: str) -> None:
    printf("run", cmd, color=COLORS.OK)
    os.system(cmd)


def add_dependencies(root_path: Path, dependencies: list[str]):
    root_path = root_path.parent
    cmd = "pip install"
    for lockfile, pm in PACKAGE_MANAGERS:
        if (root_path / lockfile).exists():
            cmd = pm

    call(f"{cmd} {' '.join(dependencies)}")


def add_to_concerns(filepath: Path, *items: str, after: str|None = None) -> None:
    """Insert a new item at the start of the concerns list.

    Arguments:
        filepath:
            Path to the Python file
        items:
            List of items to insert into the concerns lists
        after:
            If provided, insert after this item in the concerns list
            if it can be found.

    """
    content = filepath.read_text()

    # Format items and filter existing ones
    fitems = []
    for item in items:
        item = item.strip()
        if "," not in item:
            item = f"{item},"
        if item not in content:
            fitems.append(item)

    if not fitems:
        return
    tab = " " * 4
    insert = f"\n{tab * 2}" + f"\n{tab * 2}".join(fitems) + f"\n{tab}"

    # Find the class definition
    match = re.search(
        r"class AppController\(\n?\s*(Controller,)?",
        content
    )
    if not match:
        print("Could not find AppController class definition.")
        return
    insert_pos = match.end()

    # Adjust insert position if 'after' is provided
    if after:
        after_match = re.search(rf"{after},?", content[insert_pos:])
        if after_match:
            insert_pos = insert_pos + after_match.end()

    # Insert the new items
    new_content = f"{content[:insert_pos]}{insert}{content[insert_pos:]}"
    filepath.write_text(new_content)


def sort_imports(code: str) -> str:
    """
    Sort imports in the given code.
    """
    return isort.code(
        code,
        float_to_top=True,
        use_parentheses=True,
        lines_after_imports=2,
        combine_star=True,
        include_trailing_comma=True,
    )


def sort_imports_in(path: Path) -> None:
    """
    Sort imports in the given file.
    """
    code = sort_imports(path.read_text())
    path.write_text(code)
