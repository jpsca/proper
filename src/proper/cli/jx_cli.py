"""`proper jx`: the tools for the app's views, compiled by minijx."""
import json
import typing as t

from proper_cli import Cli


if t.TYPE_CHECKING:
    from ..app import App


def get_jx_cli(app: "App") -> type[Cli]:
    class JxCLI(Cli):
        """Inspect the app's views."""

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
