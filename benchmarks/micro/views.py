"""Getting a catalog of 41 components ready to render with minijx:
compiling them all (what the app does when it starts), the first render of a
page in a new catalog (loading its module), and the render in steady state.

    uv run python benchmarks/micro/views.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from _common import best_of, once
from minijx import Catalog


PAGES = 40
CARD = "{#def n #}<p>{{ n }}</p>"
PAGE = (
    '{#def title, items=[] #}{#import "card.jx" as Card #}'
    "<h1>{{ title }}</h1>{% for i in items %}<Card n={{ i }} />{% endfor %}"
)


def catalog(folder: Path, out: Path) -> Catalog:
    return Catalog(folder, output=out, auto_reload=False)


def main() -> None:
    with TemporaryDirectory() as source, TemporaryDirectory() as build:
        folder, out = Path(source), Path(build)
        (folder / "card.jx").write_text(CARD)
        for i in range(PAGES):
            (folder / f"page{i}.jx").write_text(PAGE)
        total = PAGES + 1

        compile_all = min(once(catalog(folder, out).compile) for _ in range(5))
        first = min(
            once(lambda: catalog(folder, out).render("page0.jx", title="t", items=[1, 2]))
            for _ in range(5)
        )
        loaded = catalog(folder, out)
        steady = best_of(lambda: loaded.render("page0.jx", title="t", items=[1, 2]))

        print(f"compile() of {total} components:             {compile_all:.1f} ms")
        print(f"first render of a page, new catalog:        {first:.3f} ms")
        print(f"render in steady state:                      {steady:.1f} us")


if __name__ == "__main__":
    main()
