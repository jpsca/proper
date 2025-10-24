import os
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
    "append_to_concerns",
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


def append_to_concerns(filepath: Path, items: list[str]):
    """Insert a new item at the end of each concerns list in the file.

    Arguments:
        filepath:
            Path to the Python file
        items:
            List of items to insert into the concerns lists

    """
    content = filepath.read_text()

    new_content = content
    current_pos = 0
    tab = " " * 4
    new_item = f",\n{tab * 2}".join(items)
    new_item = f"\n{tab * 2}{new_item},\n{tab}"

    while True:
        start, end = _find_concerns_bounds(new_content, current_pos)
        if start is None:
            break

        # Extract the current list content
        list_content = new_content[start:end]

        # If the list is empty or only contains whitespace
        if list_content.strip() == "[]":
            new_list_content = f"[{new_item}]"
        else:
            # Remove trailing whitespace and closing bracket
            list_content = list_content[:-1].rstrip()

            # Add the new item
            if list_content.strip().endswith(","):
                new_list_content = f"{list_content}{new_item}]"
            else:
                new_list_content = f"{list_content},{new_item}]"

        # Replace the old list with the new one
        new_content = new_content[:start] + new_list_content + new_content[end:]
        current_pos = start + len(new_list_content)

    filepath.write_text(new_content)


def _find_concerns_bounds(
    content: str,
    start_pos: int = 0,
) -> tuple[int, int] | tuple[None, None]:
    """Find the start and end positions of the next concerns list.

    Arguments:
        content:
            The file content
        start_pos:
            Position to start searching from

    Returns:
        (start_pos, end_pos) tuple of the concerns list, or (None, None) if not found

    """
    ENTRYPOINT = "concerns = ["

    # Find the start of concerns list
    start = content.find(ENTRYPOINT, start_pos)
    if start == -1:
        return None, None
    else:
        start = start + len(ENTRYPOINT) - 1

    # Find the matching closing bracket
    bracket_depth = 0
    pos = start

    while pos < len(content):
        char = content[pos]
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
            if bracket_depth == 0:
                return start, pos + 1
        pos += 1

    return None, None


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
