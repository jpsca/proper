"""`router.match` and `url_for` with 50 resources registered (100 dynamic
routes), matching the first and the last one.

Measures the route table `proper.compile.routes` builds: an index by first
path segment, then one combined regex per bucket, instead of one regex
per route tried in order.

    uv run python benchmarks/micro/routes.py
"""
from _common import best_of

from proper import Route, Router


def main() -> None:
    router = Router()
    for i in range(50):
        router.add_route(Route("GET", f"res{i}/:id<int>/items/:slug", name=f"r{i}", redirect="/x"))
        router.add_route(Route("POST", f"res{i}/:id<int>", name=f"r{i}p", redirect="/x"))
    router.lower()

    print(f"match, last of 50 resources:  {best_of(lambda: router.match('GET', '/res49/7/items/x')):.2f} us")
    print(f"match, first of 50 resources: {best_of(lambda: router.match('GET', '/res0/7/items/x')):.2f} us")
    print(f"url_for:                      {best_of(lambda: router.url_for('r49', id=7, slug='x')):.2f} us")


if __name__ == "__main__":
    main()
