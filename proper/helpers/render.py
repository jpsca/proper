import filecmp
import os
import re
import shutil
from pathlib import Path

import jinja2
from pyceo import echo, confirm


__all__ = ["BLUEPRINTS", "Render", "BlueprintRender", "printf", "get_blueprint_render", "extend_routes"]


BLUEPRINTS = (Path(__file__).parent.parent.parent / "blueprints").resolve()


class Render:
    @property
    def globals(self):
        return self.env.globals

    @property
    def filters(self):
        return self.env.filters

    @property
    def tests(self):
        return self.env.tests

    def __init__(self, templates, **envops):
        self.loader = jinja2.FileSystemLoader(str(templates))
        self.env = jinja2.Environment(
            loader=self.loader,
            autoescape=jinja2.select_autoescape(default=True),
            **envops,
        )

    def __call__(self, relpath, **context):
        return self.render(relpath, **context)

    def string(self, string, **context):
        tmpl = self.env.from_string(string)
        return tmpl.render(**context)

    def render(self, relpath, **context):
        tmpl = self.env.get_template(str(relpath))
        return tmpl.render(**context)


class BlueprintRender:
    def __init__(self, src, dst, context=None, *, envops=None, force=False):
        self.src = str(src)
        self.dst = Path(dst)
        self.force = force
        self.render = get_blueprint_render(src, context=context, envops=envops)

    def __call__(self):
        for folder, _, files in os.walk(self.src):
            self._render_folder(Path(folder), files)

    def _render_folder(self, folder, files):
        src_relfolder = str(folder).replace(self.src, "", 1).lstrip(os.path.sep)
        dst_relfolder = self.render.string(src_relfolder)
        src_relfolder = Path(src_relfolder)
        dst_relfolder = Path(dst_relfolder)

        self._make_folder(dst_relfolder)

        for name in files:
            src_path = folder / name
            src_relpath = src_relfolder / name
            name = self.render.string(name)

            if name.endswith(".tmpl"):
                dst_relpath = dst_relfolder / name[:-5]
                self._render_file(src_relpath, dst_relpath)
            elif name.endswith(".append"):
                dst_relpath = dst_relfolder / name[:-7]
                self._append_to_file(src_relpath, dst_relpath)
            else:
                dst_relpath = dst_relfolder / name
                self._copy_file(src_path, dst_relpath)

    def _make_folder(self, rel_folder):
        path = self.dst / rel_folder
        display = f"{str(rel_folder).rstrip('.')}{os.path.sep}"

        if path.exists():
            printf("exists", display)
        else:
            path.mkdir(parents=False, exist_ok=False)
            printf("created", display, color="green")

    def _render_file(self, src_relpath, dst_relpath):
        content = self.render(src_relpath)
        dst_path = self.dst / dst_relpath
        if dst_path.exists():
            if self._contents_are_identical(content, dst_path):
                printf("identical", dst_relpath)
                return
            if not self._confirm_overwrite(dst_relpath):
                printf("skipped", dst_relpath, color="yellow")
                return
            printf("updated", dst_relpath, color="yellow")
        else:
            printf("created", dst_relpath, color="green")

        dst_path.write_text(content)

    def _append_to_file(self, src_relpath, dst_relpath):
        dst_path = self.dst / dst_relpath
        verb = "extended" if dst_path.exists() else "created"
        printf(verb, dst_relpath, color="green")

        dst_path.touch(exist_ok=True)
        curr_content = dst_path.read_text()
        if not curr_content.endswith("\n"):
            curr_content += "\n"
        new_content = self.render(src_relpath)
        dst_path.write_text(curr_content + new_content)


    def _copy_file(self, src_path, dst_relpath):
        dst_path = self.dst / dst_relpath
        if dst_path.exists():
            if self._files_are_identical(src_path, dst_path):
                printf("identical", dst_relpath)
                return
            if not self._confirm_overwrite(dst_relpath):
                printf("skipped", dst_relpath, color="yellow")
                return
            printf("updated", dst_relpath, color="yellow")
        else:
            printf("created", dst_relpath, color="green")

        shutil.copy2(str(src_path), str(dst_path))

    def _files_are_identical(self, src_path, dst_path):
        return filecmp.cmp(str(src_path), str(dst_path), shallow=False)

    def _contents_are_identical(self, content, dst_path):
        return content == dst_path.read_text()

    def _confirm_overwrite(self, dst_relpath):
        printf("conflict", dst_relpath, color="red")
        if self.force:
            return True
        return confirm(" Overwrite?")


def printf(verb, msg="", color="cyan", indent=10):
    verb = str(verb).rjust(indent, " ")
    verb = f"<fg:{color}>{verb}</fg>"
    echo(f"{verb}  {msg}".rstrip())


def get_blueprint_render(src, context=None, *, envops=None):
    envops = envops or {}
    envops.setdefault("block_start_string", "[%")
    envops.setdefault("block_end_string", "%]")
    envops.setdefault("variable_start_string", "[[")
    envops.setdefault("variable_end_string", "]]")
    envops.setdefault("keep_trailing_newline", True)
    render = Render(src, **(envops or {}))
    render.globals.update(context or {})
    return render


RE_CLOSE_ROUTES = re.compile(r",?[\s\n]*][\s\n]*$")


def extend_routes(app, new_routes):
    routes_path = app.root_path / "routes.py"
    routes = routes_path.read_text()
    match = RE_CLOSE_ROUTES.search(routes)
    if match:
        routes = routes[: match.start()].rstrip()
    routes_path.write_text(routes + new_routes)
    printf("updated", str(routes_path), color="yellow")
