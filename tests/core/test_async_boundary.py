"""Tests for the sync/async boundary: "sync above, async below".

Application code runs in a worker thread. The event loop above it must never
be the one waiting on a file, and the context it hands down only travels one
way.
"""
import asyncio
import time

import pytest

from proper import App, current
from proper.core.response.file_wrapper import FileWrapper
from proper.helpers.asgi import make_test_scope


@pytest.fixture()
def app():
    return App("proper", {"SECRET_KEYS": ["*" * 50], "DEBUG": False})


class SlowFile:
    """A file whose reads block, like a cold disk or a network mount."""

    def __init__(self, chunks: int, delay: float = 0.05) -> None:
        self.chunks = chunks
        self.delay = delay
        self.closed = False

    def read(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        self.chunks -= 1
        time.sleep(self.delay)
        return b"x" * 10

    def close(self) -> None:
        self.closed = True


async def run_request(app, path="/"):
    scope = make_test_scope(path)
    scope["app"] = app

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    await app.asgi_app(scope, receive, send)
    return sent


async def measure_worst_stall(coro):
    """Run `coro` while timing how long the loop goes without a turn."""
    gaps = []
    running = True

    async def heartbeat():
        last = time.perf_counter()
        while running:
            await asyncio.sleep(0)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    task = asyncio.create_task(heartbeat())
    await asyncio.sleep(0)
    result = await coro
    running = False
    await task
    return result, max(gaps)


class TestStreamingDoesNotBlockTheLoop:
    async def test_file_chunks_are_read_off_the_loop(self, app):
        source = SlowFile(chunks=6, delay=0.05)

        def stream(self, request, response):
            response.body = FileWrapper(source, block_size=10)
            response.headers["content-length"] = "60"
            return response

        app._run_pipeline = stream.__get__(app, App)

        sent, worst_stall = await measure_worst_stall(run_request(app, "/file.bin"))

        body = b"".join(
            m.get("body", b"") for m in sent if m["type"] == "http.response.body"
        )
        assert body == b"x" * 60
        # The reads add up to ~300ms; none of it may happen on the loop.
        assert worst_stall < 0.04, f"loop blocked for {worst_stall * 1000:.0f} ms"

    async def test_the_file_is_closed_after_streaming(self, app):
        source = SlowFile(chunks=2, delay=0)

        def stream(self, request, response):
            response.body = FileWrapper(source, block_size=10)
            response.headers["content-length"] = "20"
            return response

        app._run_pipeline = stream.__get__(app, App)
        await run_request(app, "/file.bin")
        assert source.closed

    async def test_the_file_is_closed_when_sending_fails(self, app):
        source = SlowFile(chunks=5, delay=0)

        def stream(self, request, response):
            response.body = FileWrapper(source, block_size=10)
            response.headers["content-length"] = "50"
            return response

        app._run_pipeline = stream.__get__(app, App)

        scope = make_test_scope("/file.bin")
        scope["app"] = app

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message.get("more_body"):
                raise ConnectionResetError("client went away")

        with pytest.raises(ConnectionResetError):
            await app.asgi_app(scope, receive, send)

        assert source.closed

    async def test_an_iterable_without_close_streams_fine(self, app):
        """`prepare()` passes any iterable through, not just `FileWrapper`."""

        def stream(self, request, response):
            response.body = [b"one", b"two", b"three"]
            response.headers["content-length"] = "11"
            return response

        app._run_pipeline = stream.__get__(app, App)
        sent = await run_request(app, "/chunks")

        body = b"".join(
            m.get("body", b"") for m in sent if m["type"] == "http.response.body"
        )
        assert body == b"onetwothree"


class TestContextBarrier:
    async def test_the_pipeline_context_does_not_leak_back_to_the_loop(self, app):
        """`asyncio.to_thread` copies the context downwards only.

        Anything the pipeline writes to `current` is gone by the time the
        loop resumes, so nothing above the boundary - `response.prepare()`
        or the streaming loop - may rely on it.
        """
        inside = {}

        def pipeline(self, request, response):
            current.user = "alice"
            inside["user"] = current.user
            response.body = b"ok"
            return response

        app._run_pipeline = pipeline.__get__(app, App)

        current.user = None
        await run_request(app)

        assert inside["user"] == "alice"
        assert current.user is None

    async def test_the_request_is_visible_on_both_sides(self, app):
        """What the loop sets *before* the hop does travel down, which is
        why `current.request` works in a controller."""
        seen = {}

        def pipeline(self, request, response):
            seen["request"] = current.request
            response.body = b"ok"
            return response

        app._run_pipeline = pipeline.__get__(app, App)
        await run_request(app, "/somewhere")

        assert seen["request"] is not None
        assert seen["request"].path == "/somewhere"
        assert current.request.path == "/somewhere"
