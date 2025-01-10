import filecmp
import os
import shutil
import typing as t
from fnmatch import fnmatch
from pathlib import Path

import isort
import jinja2
from proper_cli import confirm, echo


__all__ = [
    "BLUEPRINTS",
    "Render",
    "BlueprintRender",
    "make_folder",
    "copy_file",
    "add_dependencies",
    "append_to_file",
    "prepend_to_file",
    "save_file",
    "get_blueprint_render",
    "printf",
    "call",
    "files_are_identical",
    "contents_are_identical",
    "confirm_overwrite",
    "sort_imports",
    "sort_imports_in",
    "append_to_concerns",
]

BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()
IGNORE = [".DS_Store", "__pycache__", "*/__pycache__", "*/.DS_Store"]

CREATE = "create"
UPDATE = "update"
SKIPPED = "skipped"
IDENTICAL = "identical"
PREPEND = "prepend"
APPEND = "append"
RUN = "run"

COLOR_OK = "green"
COLOR_WARNING = "yellow"
COLOR_CONFLICT = "red"


class Render:
    def __init__(self, templates: str | Path, **envops) -> None:
        self.loader = jinja2.FileSystemLoader(str(templates))
        self.env = jinja2.Environment(
            loader=self.loader,
            autoescape=jinja2.select_autoescape(default=True),
            **envops,
        )
        self.env.globals["render"] = self.render

    @property
    def globals(self) -> dict:
        return self.env.globals

    @property
    def filters(self) -> dict:
        return self.env.filters

    @property
    def tests(self) -> dict:
        return self.env.tests

    def __call__(self, relpath: str | Path, **context) -> str:
        return self.render(relpath, **context)

    def string(self, string: str, **context) -> str:
        tmpl = self.env.from_string(string)
        return tmpl.render(**context)

    def render(self, relpath: str | Path, **context) -> str:
        tmpl = self.env.get_template(str(relpath))
        return tmpl.render(**context)


class BlueprintRender:
    def __init__(
        self,
        src: str | Path,
        dst: str | Path,
        context: dict | None = None,
        *,
        ignore: list[str] | None = None,
        envops: dict | None = None,
        force=False,
    ) -> None:
        self.src = Path(src)
        self.dst = Path(dst)
        self.force = force
        self.render = get_blueprint_render(self.src, context=context, envops=envops)
        self.ignore = ignore or IGNORE

    def __call__(self) -> None:
        for folder, _, files in os.walk(self.src):
            self.render_folder(Path(folder), files)

    def render_folder(self, folder: Path, files: list[str]) -> None:
        if self._ignore(folder):
            return
        _src_relfolder = str(folder).replace(str(self.src), "", 1).lstrip(os.path.sep)
        _dst_relfolder = self.render.string(_src_relfolder)
        src_relfolder = Path(_src_relfolder)
        dst_relfolder = Path(_dst_relfolder)

        make_folder(self.dst, dst_relfolder)

        for name in files:
            src_relpath = src_relfolder / name
            if self._ignore(src_relpath):
                continue
            name = self.render.string(name)

            if ".tt." in name or name.endswith(".tt"):
                dst_name = name.replace(".tt", "")
                dst_relpath = dst_relfolder / dst_name
                content = self.render(src_relpath)
                save_file(self.dst, dst_relpath, content, force=self.force)
            elif ".append." in name or name.endswith(".append"):
                dst_name = name.replace(".append", "")
                dst_relpath = dst_relfolder / dst_name
                content = self.render(src_relpath)
                append_to_file(self.dst, dst_relpath, content)
            elif ".prepend." in name or name.endswith(".prepend"):
                dst_name = name.replace(".prepend", "")
                dst_relpath = dst_relfolder / dst_name
                content = self.render(src_relpath)
                prepend_to_file(self.dst, dst_relpath, content)
            else:
                dst_relpath = dst_relfolder / name
                copy_file(self.src / src_relpath, self.dst, dst_relpath)

    def _ignore(self, path: Path) -> bool:
        name = path.name
        str_path = str(path)
        for pattern in self.ignore:
            if fnmatch(name, pattern) or fnmatch(str_path, pattern):
                return True
        return False


def make_folder(root_path: Path, rel_folder: str | Path) -> None:
    path = root_path / rel_folder
    if path.exists():
        return

    rel_folder = str(rel_folder).rstrip(".")
    display = f"{rel_folder}{os.path.sep}"
    path.mkdir(parents=True, exist_ok=False)
    if rel_folder:
        printf(CREATE, display, color=COLOR_OK)


def copy_file(
    src_path: Path, root_path: Path, dst_relpath: str | Path, *, force=False
) -> None:
    dst_path = root_path / dst_relpath
    if dst_path.exists():
        if files_are_identical(src_path, dst_path):
            printf(IDENTICAL, dst_relpath)
            return
        if not confirm_overwrite(dst_relpath, force=force):
            printf(SKIPPED, dst_relpath, color=COLOR_WARNING)
            return
        printf(UPDATE, dst_relpath, color=COLOR_WARNING)
    else:
        printf(CREATE, dst_relpath, color=COLOR_OK)

    shutil.copy2(str(src_path), str(dst_path))


PACKAGE_MANAGERS = {
    ("poetry.lock", "poetry add"),
    ("uv.lock", "uv add"),
}


def add_dependencies(root_path: Path, dependencies: list[str]):
    root_path = root_path.parent
    cmd = "pip install"
    for lockfile, pm in PACKAGE_MANAGERS:
        if (root_path / lockfile).exists():
            cmd = pm

    call(f"{cmd} {' '.join(dependencies)}")


def append_to_file(root_path: Path, dst_relpath: str | Path, new_content: str) -> None:
    dst_path = root_path / dst_relpath
    if dst_path.exists():
        curr_content = dst_path.read_text()
        if new_content in curr_content:
            printf(SKIPPED, dst_relpath, color=COLOR_WARNING)
            return

        if not curr_content.endswith("\n"):
            curr_content += "\n"
        new_content = curr_content + new_content
        printf(APPEND, dst_relpath, color=COLOR_WARNING)
    else:
        dst_path.touch(exist_ok=True)
        printf(CREATE, dst_relpath, color=COLOR_OK)

    dst_path.write_text(new_content)


def prepend_to_file(root_path: Path, dst_relpath: str | Path, new_content: str) -> None:
    dst_path = root_path / dst_relpath
    if dst_path.exists():
        curr_content = dst_path.read_text()
        if new_content in curr_content:
            printf(SKIPPED, dst_relpath, color=COLOR_WARNING)
            return

        if not new_content.endswith("\n"):
            new_content += "\n"
        new_content = new_content + curr_content
        printf(PREPEND, dst_relpath, color=COLOR_WARNING)
    else:
        dst_path.touch(exist_ok=True)
        printf(CREATE, dst_relpath, color=COLOR_OK)

    dst_path.write_text(new_content)


def save_file(
    root_path: Path, dst_relpath: str | Path, content: str, *, force=False
) -> None:
    dst_path = root_path / dst_relpath
    if dst_path.exists():
        if contents_are_identical(content, dst_path):
            printf(IDENTICAL, dst_relpath)
            return
        if not confirm_overwrite(dst_relpath, force=force):
            printf(SKIPPED, dst_relpath, color=COLOR_WARNING)
            return
        printf(UPDATE, dst_relpath, color=COLOR_WARNING)
    else:
        printf(CREATE, dst_relpath, color=COLOR_OK)

    dst_path.write_text(content)


def get_blueprint_render(
    src: Path, context: dict | None = None, *, envops: dict | None = None
) -> Render:
    envops = envops or {}
    envops.setdefault("block_start_string", "[%")
    envops.setdefault("block_end_string", "%]")
    envops.setdefault("variable_start_string", "[[")
    envops.setdefault("variable_end_string", "]]")
    envops.setdefault("comment_start_string", "[#")
    envops.setdefault("comment_end_string", "#]")
    envops.setdefault("keep_trailing_newline", True)
    envops["undefined"] = jinja2.StrictUndefined
    render = Render(src, **(envops or {}))
    render.globals.update(context or {})
    return render


def printf(
    verb: str,
    msg: t.Any = "",
    color: str = "cyan",
    indent: int = 10,
) -> None:
    verb = str(verb).rjust(indent, " ")
    verb = f"<fg={color}>{verb}</>"
    echo(f"{verb}  {msg}".rstrip())


def call(cmd: str) -> None:
    printf(RUN, cmd, color=COLOR_OK)
    os.system(cmd)


def files_are_identical(src_path: Path, dst_path: Path) -> bool:
    return filecmp.cmp(str(src_path), str(dst_path), shallow=False)


def contents_are_identical(content: str, dst_path: Path) -> bool:
    return content == dst_path.read_text()


def confirm_overwrite(dst_relpath: str | Path, *, force=False) -> bool:
    printf("conflict", dst_relpath, color=COLOR_CONFLICT)
    if force:
        return True
    return confirm(" Overwrite?")


def sort_imports(code: str) -> str:
    return isort.code(
        code,
        float_to_top=True,
        use_parentheses=True,
        lines_after_imports=2,
        combine_star=True,
        include_trailing_comma=True,
    )


def sort_imports_in(path: Path) -> None:
    code = sort_imports(path.read_text())
    path.write_text(code)


def find_concerns_bounds(
    content: str,
    start_pos: int = 0,
) -> tuple[int, int] | tuple[None, None]:
    """Find the start and end positions of the next concerns list.

    Parameters
    ----------
    content:
        The file content
    start_pos:
        Position to start searching from

    Returns
    -------
    tuple (start_pos, end_pos) of the concerns list, or (None, None) if not found

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


def append_to_concerns(filepath: Path, items: list[str]):
    """Insert a new item at the end of each concerns list in the file.

    Parameters
    ----------
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
        start, end = find_concerns_bounds(new_content, current_pos)
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
