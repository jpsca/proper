"""`proper jx`: the tools for the app's views, compiled by minijx."""
import json
import sys
import typing as t

from minijx import CompileError
from proper_cli import Cli

from ..compile import compile_views


if t.TYPE_CHECKING:
    from ..app import App


def get_jx_cli(app: "App") -> type[Cli]:
    class JxCLI(Cli):
        """Inspect and compile the app's views."""

        def compile(self):
            """Compile every view of the app now, instead of when it starts.

            Run it when the app is built for production, e.g. in its
            Dockerfile: outside of debug mode, an app whose views are already
            compiled starts without compiling them again, so it starts faster
            and does not need to write to the folder of the compiled views.

            It ends with an error, listing every view that does not compile.
            """
            catalog = app.catalog
            try:
                compiled = compile_views(app, force=True)
            except CompileError as err:
                print(err, file=sys.stderr)
                sys.exit(1)
            if not compiled:
                print("There is no minijx compiler for this platform.", file=sys.stderr)
                sys.exit(1)
            count = sum(1 for folder in catalog.folders for _ in folder.rglob("*.jx"))
            print(f"Compiled {count} views into {catalog.output}")

        def info(self, format: str = "text"):
            """Report the catalog's folders, where the views are compiled,
            the extensions with autoescape, the custom tags and the views.

            Arguments:
            - format:
                "text" (default) or "json".
            """
            catalog = app.catalog
            views = sorted(
                p.relative_to(folder).as_posix()
                for folder in catalog.folders
                for p in folder.rglob("*.jx")
            )
            data = {
                "folders": [str(f) for f in catalog.folders],
                "output": str(catalog.output),
                "autoescape": list(catalog.autoescape),
                "tags": list(catalog.tags),
                "views": views,
            }
            if format == "json":
                print(json.dumps(data, indent=2))
                return
            print(f"Folders:    {', '.join(data['folders'])}")
            print(f"Compiled:   {data['output']}")
            print(f"Autoescape: {', '.join(data['autoescape']) or '-'}")
            print(f"Tags:       {', '.join(data['tags']) or '-'}")
            print(f"Views:      {len(views)}")
            for name in views:
                print(f"  {name}")

    return JxCLI
