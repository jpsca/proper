"""Tests for the DEBUG-only event loop instrumentation."""
import asyncio
import logging
import time

import pytest

from proper import App
from proper.core.loop_debug import LoopWatchdog, enable_asyncio_debug


@pytest.fixture(autouse=True)
def _restore_loop_debug():
    """No test may leave the loop in debug mode for the next one."""
    yield
    try:
        asyncio.get_running_loop().set_debug(False)
    except RuntimeError:
        pass


def make_app(**config):
    return App("proper", {"SECRET_KEYS": ["*" * 50], **config})


def block_the_loop(seconds):
    """A named frame to look for in the reported stack."""
    time.sleep(seconds)


async def settle(watchdog):
    """Give the watchdog thread a couple of turns to notice."""
    await asyncio.sleep(watchdog._interval * 3)


class TestEnableAsyncioDebug:
    async def test_it_turns_on_the_loops_own_checks(self):
        loop = asyncio.get_running_loop()
        assert not loop.get_debug()

        enable_asyncio_debug(0.25)

        assert loop.get_debug()
        assert loop.slow_callback_duration == 0.25

        loop.set_debug(False)


class TestLoopWatchdog:
    async def test_it_warns_when_the_loop_is_blocked(self, caplog):
        watchdog = LoopWatchdog(0.05)
        with caplog.at_level(logging.WARNING, logger="proper"):
            watchdog.start()
            await asyncio.sleep(0.05)
            block_the_loop(0.3)
            await settle(watchdog)
            await watchdog.stop()

        assert "the event loop has been blocked" in caplog.text

    async def test_the_warning_points_at_the_blocking_code(self, caplog):
        watchdog = LoopWatchdog(0.05)
        with caplog.at_level(logging.WARNING, logger="proper"):
            watchdog.start()
            await asyncio.sleep(0.05)
            block_the_loop(0.3)
            await settle(watchdog)
            await watchdog.stop()

        assert "block_the_loop" in caplog.text

    async def test_it_stays_quiet_while_the_loop_is_free(self, caplog):
        watchdog = LoopWatchdog(0.05)
        with caplog.at_level(logging.WARNING, logger="proper"):
            watchdog.start()
            # Plenty of waiting, none of it blocking.
            for _ in range(20):
                await asyncio.sleep(0.02)
            await watchdog.stop()

        assert "blocked" not in caplog.text

    async def test_one_warning_per_stall(self, caplog):
        watchdog = LoopWatchdog(0.05)
        with caplog.at_level(logging.WARNING, logger="proper"):
            watchdog.start()
            await asyncio.sleep(0.05)
            block_the_loop(0.4)
            await settle(watchdog)
            await watchdog.stop()

        warnings = [r for r in caplog.records if "blocked" in r.getMessage()]
        assert len(warnings) == 1

    async def test_stop_is_safe_before_start(self):
        await LoopWatchdog(0.05).stop()

    async def test_work_in_a_worker_thread_is_not_a_stall(self, caplog):
        """The whole point: the same sleep, moved off the loop, is fine."""
        watchdog = LoopWatchdog(0.05)
        with caplog.at_level(logging.WARNING, logger="proper"):
            watchdog.start()
            await asyncio.to_thread(block_the_loop, 0.3)
            await settle(watchdog)
            await watchdog.stop()

        assert "blocked" not in caplog.text


class TestAppWiring:
    async def test_it_is_off_by_default(self):
        app = make_app(DEBUG=False)
        app._start_loop_debug()
        try:
            assert app._loop_watchdog is None
            assert not asyncio.get_running_loop().get_debug()
        finally:
            await app._stop_loop_debug()

    async def test_it_starts_in_debug(self):
        app = make_app(DEBUG=True)
        app._start_loop_debug()
        try:
            assert app._loop_watchdog is not None
            assert asyncio.get_running_loop().get_debug()
        finally:
            await app._stop_loop_debug()
            asyncio.get_running_loop().set_debug(False)

    async def test_stopping_clears_the_watchdog(self):
        app = make_app(DEBUG=True)
        app._start_loop_debug()
        await app._stop_loop_debug()
        assert app._loop_watchdog is None
        asyncio.get_running_loop().set_debug(False)

    async def test_run_sync_keeps_it_off(self):
        """Under RUN_SYNC the pipeline runs on the loop on purpose."""
        app = make_app(DEBUG=True, RUN_SYNC=True)
        app._start_loop_debug()
        try:
            assert app._loop_watchdog is None
            assert not asyncio.get_running_loop().get_debug()
        finally:
            await app._stop_loop_debug()

    async def test_a_zero_threshold_turns_it_off(self):
        app = make_app(DEBUG=True, LOOP_STALL_WARNING=0)
        app._start_loop_debug()
        try:
            assert app._loop_watchdog is None
            assert not asyncio.get_running_loop().get_debug()
        finally:
            await app._stop_loop_debug()

    async def test_the_threshold_comes_from_the_config(self):
        app = make_app(DEBUG=True, LOOP_STALL_WARNING=0.5)
        app._start_loop_debug()
        try:
            assert app._loop_watchdog.threshold == 0.5
            assert asyncio.get_running_loop().slow_callback_duration == 0.5
        finally:
            await app._stop_loop_debug()
            asyncio.get_running_loop().set_debug(False)


class TestLifespan:
    async def test_the_watchdog_runs_for_the_life_of_the_app(self):
        app = make_app(DEBUG=True)
        messages = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
        sent = []
        watching = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message["type"])
            if message["type"] == "lifespan.startup.complete":
                watching.append(app._loop_watchdog)

        await app.asgi_app({"type": "lifespan"}, receive, send)

        assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]
        assert isinstance(watching[0], LoopWatchdog)
        assert app._loop_watchdog is None
        asyncio.get_running_loop().set_debug(False)
