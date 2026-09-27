"""`proper jx`: the Jx component tools, pointed at the app's catalog.

The standalone `jx` command took the catalog as a `module:attribute` path.
Here the app already built it, so the commands take no such argument.
"""
import sys
import typing as t

from proper_cli import Cli

from ..jx.cli import run_parse
from ..jx.tools import check, info


if t.TYPE_CHECKING:
    from ..app import App


def get_jx_cli(app: "App") -> type[Cli]:
    class JxCLI(Cli):
        """Check and inspect the app's Jx components."""

        def check(self, format: str = "text"):
            """Validate every component in the app's views: imports that
            resolve, tags that name an imported component, props that exist.
            Exits with 1 if any component has errors.

            Arguments:

            - format:
                "text" (default) or "json".

            """
            code = check(app.catalog, format=format)
            if code:
                sys.exit(code)

        def info(self, format: str = "text"):
            """Report the catalog's folders, prefixes, file extension
            and the components it found.

            Arguments:

            - format:
                "text" (default) or "json".

            """
            info(app.catalog, format=format)

        def parse(self, file: str, stdin: bool = False, format: str = "json"):
            """Report one component's imports and component tags, with
            their positions. Exits with 1 if the file has syntax errors.

            Arguments:

            - file:
                Path to the component file.
            - stdin:
                Read the source from stdin, using `file` only as its name
                (for an editor buffer that has not been saved).
            - format:
                "json" (default) or "text".

            """
            code = run_parse(file, use_stdin=stdin, format=format)
            if code:
                sys.exit(code)

        def collect_assets(self, output: str):
            """Copy the assets of the catalog's package folders (the ones
            registered with a prefix) into one output folder.

            Arguments:

            - output:
                Destination folder.

            """
            collected = app.catalog.collect_assets(output)
            for prefix, rel in collected:
                print(f"  {prefix}/{rel}" if prefix else f"  {rel}")
            print(f"\n{len(collected)} file{'s' if len(collected) != 1 else ''} collected")

    return JxCLI
