"""Tests for the pool of threads that runs the application's code."""
import asyncio
import logging
import threading
import time

import pytest

from proper import App
from proper.app import _default_max_threads, _ThreadWaits
from proper.helpers.asgi import make_test_scope


def make_app(**config):
    return App("proper", {"SECRET_KEYS": ["*" * 50], **config})


async def run_requests(app, count, work=0.1):
    """Fire `count` requests at once, each holding a thread for `work`."""
    threads = set()

    def pipeline(self, request, response):
        threads.add(threading.current_thread().name)
        time.sleep(work)
        response.body = b"ok"
        return response

    app._run_pipeline = pipeline.__get__(app, App)

    async def one():
        scope = make_test_scope("/")
        scope["app"] = app

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await app.asgi_app(scope, receive, send)

    started = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(count)])
    return threads, time.perf_counter() - started


@pytest.fixture()
async def executor_cleanup():
    """Stop the pool a test installed. Each test gets its own loop, so
    there is nothing to hand back - only threads to wind down."""
    yield
    await asyncio.get_running_loop().shutdown_default_executor()


class TestPoolSize:
    def test_the_default_matches_pythons(self):
        app = make_app()
        assert app.max_threads == _default_max_threads()

    def test_the_config_sets_it(self):
        assert make_app(MAX_THREADS=3).max_threads == 3

    async def test_the_pool_is_capped(self, executor_cleanup):
        app = make_app(MAX_THREADS=2)
        app._setup_executor()

        threads, elapsed = await run_requests(app, 6, work=0.05)

        assert len(threads) == 2
        # Six requests through two threads is three rounds, not one.
        assert elapsed >= 0.15

    async def test_the_threads_say_who_they_belong_to(self, executor_cleanup):
        app = make_app(MAX_THREADS=1)
        app._setup_executor()

        threads, _ = await run_requests(app, 1, work=0)

        assert all(name.startswith("proper-worker") for name in threads)


class TestQueueWarning:
    async def test_it_warns_when_every_thread_is_busy(
        self, caplog, executor_cleanup
    ):
        app = make_app(MAX_THREADS=1, THREAD_WAIT_WARNING=0.02)
        app._setup_executor()

        with caplog.at_level(logging.WARNING, logger="proper"):
            await run_requests(app, 3, work=0.05)

        assert "queued for a worker thread" in caplog.text
        assert "all 1 are busy" in caplog.text

    async def test_it_stays_quiet_when_the_pool_keeps_up(
        self, caplog, executor_cleanup
    ):
        app = make_app(MAX_THREADS=4, THREAD_WAIT_WARNING=0.5)
        app._setup_executor()

        with caplog.at_level(logging.WARNING, logger="proper"):
            await run_requests(app, 4, work=0.01)

        assert "queued for a worker thread" not in caplog.text

    async def test_zero_turns_the_check_off(self, caplog, executor_cleanup):
        app = make_app(MAX_THREADS=1, THREAD_WAIT_WARNING=0)
        app._setup_executor()

        with caplog.at_level(logging.WARNING, logger="proper"):
            await run_requests(app, 3, work=0.05)

        assert "queued for a worker thread" not in caplog.text

    async def test_one_warning_covers_a_whole_pile_up(
        self, caplog, executor_cleanup
    ):
        """A saturated pool must not log once per queued request."""
        app = make_app(MAX_THREADS=1, THREAD_WAIT_WARNING=0.01)
        app._setup_executor()

        with caplog.at_level(logging.WARNING, logger="proper"):
            await run_requests(app, 12, work=0.02)

        warnings = [
            record for record in caplog.records
            if "queued for a worker thread" in record.getMessage()
        ]
        assert len(warnings) == 1


class TestThreadWaits:
    def test_the_first_wait_reports_straight_away(self):
        assert _ThreadWaits().record(0.5, interval=10) == (1, 0.5)

    def test_later_waits_are_held_back(self):
        waits = _ThreadWaits()
        waits.record(0.5, interval=10)
        assert waits.record(0.7, interval=10) is None

    def test_the_next_report_carries_what_was_held_back(self):
        waits = _ThreadWaits()
        waits.record(0.5, interval=10)
        waits.record(0.7, interval=10)
        waits.record(2.0, interval=10)
        # The first report reset the tally, so this one carries the three
        # waits since, the longest of them 2.0s.
        assert waits.record(0.1, interval=0) == (3, 2.0)

    def test_counting_survives_many_threads(self):
        waits = _ThreadWaits()
        waits.record(0.1, interval=10)  # consumes the first report

        def hammer():
            for _ in range(2000):
                waits.record(0.1, interval=10)

        threads = [threading.Thread(target=hammer) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        count, _ = waits.record(0.1, interval=0)
        assert count == 6 * 2000 + 1
