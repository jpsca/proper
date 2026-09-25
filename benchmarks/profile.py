"""Profile the framework's own cost per request, in process, without a server.

    uv run python -m benchmarks.profile [/plaintext] [--requests 20000] [--sort tottime|cumtime]

Runs the benchmark app's route through `App.__rsgi__` with the test stubs,
on one thread (`RUN_SYNC`), so the profile shows the pipeline alone: no
Granian, no event loop hop, no worker thread. Prints the time per request
without the profiler, then the profile.
"""
import argparse
import asyncio
import cProfile
import io
import pstats
import time

from benchmarks.app import make_app
from proper.test_client import HttpProtocolStub, make_test_scope


HEADERS = [("host", "127.0.0.1:8123"), ("user-agent", "bombardier"), ("accept", "*/*")]


async def run(app, scope, count: int) -> None:
    for _ in range(count):
        protocol = HttpProtocolStub()
        await app.__rsgi__(scope, protocol)
        assert protocol.status == 200, protocol.status


async def main(path: str, requests: int, sort: str) -> None:
    app = make_app()
    app.config.RUN_SYNC = True
    scope = make_test_scope(path, headers=HEADERS)

    await run(app, scope, 500)  # warm up
    started = time.perf_counter()
    await run(app, scope, requests)
    per_request = (time.perf_counter() - started) / requests * 1e6
    print(f"{path}: {per_request:.1f} us/request, single thread, no server\n")

    profiler = cProfile.Profile()
    profiler.enable()
    await run(app, scope, requests // 4)
    profiler.disable()
    out = io.StringIO()
    stats = pstats.Stats(profiler, stream=out).sort_stats(sort)
    stats.print_stats("proper/src" if sort == "cumtime" else 40, 45)
    print(out.getvalue())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="/plaintext")
    ap.add_argument("--requests", type=int, default=20000)
    ap.add_argument("--sort", choices=("tottime", "cumtime"), default="tottime")
    args = ap.parse_args()
    asyncio.run(main(args.path, args.requests, args.sort))
