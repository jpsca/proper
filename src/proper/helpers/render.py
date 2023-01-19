import filecmp
import os
import re
import shutil
import typing as t
from fnmatch import fnmatch
from pathlib import Path

import jinja2
import isort
from proper_cli import confirm, echo

if t.TYPE_CHECKING:
    from proper import App


__all__ = [
    "BLUEPRINTS",
    "Render",
    "BlueprintRender",
    "printf",
    "call",
    "get_blueprint_render",
    "append_routes",
]

BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()
IGNORE = [".DS_Store", "__pycache__"]

CREATE = "create"
UPDATE = "update"
SKIPPED = "skipped"
IDENTICAL = "identical"
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

            if ".tmpl." in name or name.endswith(".tmpl"):
                dst_name = name.replace(".tmpl", "")
                dst_relpath = dst_relfolder / dst_name
                content = self.render(src_relpath)
                save_file(self.dst, dst_relpath, content, force=self.force)
            elif ".append." in name or name.endswith(".append"):
                dst_name = name.replace(".append", "")
                dst_relpath = dst_relfolder / dst_name
                content = self.render(src_relpath)
                append_to_file(self.dst, dst_relpath, content)
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


def printf(verb: str, msg="", color="cyan", indent=10) -> None:
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


RE_CLOSE_ROUTES = re.compile(r",?[\s\n]*][\s\n]*$")


def append_routes(app: "App", new_routes: str) -> None:
    routes_path = app.root_path / "routes.py"
    routes = routes_path.read_text()
    if new_routes in routes:
        return

    match = RE_CLOSE_ROUTES.search(routes)
    if match:
        routes = routes[: match.start()].rstrip()

    code = sort_imports(f"{routes}{new_routes}")
    routes_path.write_text(code)

    display = str(Path(app.root_path.name) / "routes.py")
    printf(UPDATE, display, color=COLOR_WARNING)


def sort_imports(code: str) -> str:
    return isort.code(
        code,
        float_to_top=True,
        use_parentheses=True,
        lines_after_imports=2,
        combine_star=True,
        include_trailing_comma=True,
    )
