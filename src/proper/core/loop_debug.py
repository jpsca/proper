"""Event-loop instrumentation for DEBUG mode.

Proper runs every piece of application code in a worker thread ("sync above,
async below"), so the event loop should never stay busy for more than a
moment. What follows watches for the loop being blocked anyway, which means
work that belongs in a worker thread is running on the loop instead.
"""
import asyncio
import sys
import threading
import time
import traceback

from ..helpers import logger


__all__ = ("LoopWatchdog", "enable_asyncio_debug")

# Don't wake up more often than this, no matter how low the threshold is.
MIN_INTERVAL = 0.01


def enable_asyncio_debug(threshold: float) -> None:
    """Turn on asyncio's own debug checks for the running loop.

    These catch calls into the loop from the wrong thread, coroutines that
    are never awaited, and tasks collected while still pending.

    They also report slow callbacks, but not the ones that matter most here:
    since Python 3.13, a callback resumed by `asyncio.to_thread()` - which is
    how every Proper request comes back to the loop - is not measured.
    `LoopWatchdog` is what covers that.
    """
    loop = asyncio.get_running_loop()
    loop.set_debug(True)
    loop.slow_callback_duration = threshold


class LoopWatchdog:
    """Warns when the event loop stays busy for longer than `threshold`.

    A blocked event loop cannot report on itself: a task that measures the
    delay only runs once the delay is over, when whatever caused it is gone.
    So the check runs on its own thread. A task on the loop refreshes a
    timestamp, and the thread notices when those refreshes stop arriving.
    Being awake *during* the stall, it can dump what the loop thread is busy
    with at that very moment.

    Arguments:
        threshold:
            Seconds the loop may stay busy before a warning is logged.

    """

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold
        self._interval = max(MIN_INTERVAL, threshold / 2)
        self._beat = time.monotonic()
        self._loop_thread_id = threading.get_ident()
        self._stop = threading.Event()
        self._task: "asyncio.Task | None" = None

    def start(self) -> None:
        """Start watching. Call this from the event loop thread."""
        self._loop_thread_id = threading.get_ident()
        self._beat = time.monotonic()
        self._stop.clear()
        self._task = asyncio.create_task(self._heartbeat())
        threading.Thread(
            target=self._watch,
            name="proper-loop-watchdog",
            daemon=True,
        ).start()
        logger.info(
            "[loop] watching for stalls longer than %.0f ms",
            self.threshold * 1000,
        )

    async def stop(self) -> None:
        """Stop watching."""
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _heartbeat(self) -> None:
        """Runs on the event loop: says "the loop is alive" on every tick."""
        while True:
            self._beat = time.monotonic()
            await asyncio.sleep(self._interval)

    def _watch(self) -> None:
        """Runs on its own thread: reports beats that never arrived."""
        reported = 0.0
        while not self._stop.wait(self._interval):
            beat = self._beat
            stalled = time.monotonic() - beat
            # One warning per stall, not one per check.
            if stalled >= self.threshold and beat != reported:
                reported = beat
                self._report(stalled)

    def _report(self, stalled: float) -> None:
        frame = sys._current_frames().get(self._loop_thread_id)
        stack = (
            "".join(traceback.format_stack(frame))
            if frame is not None
            else "  (the loop thread is gone)\n"
        )
        logger.warning(
            "[loop] the event loop has been blocked for %.0f ms."
            " This work belongs in a worker thread:\n%s",
            stalled * 1000,
            stack,
        )
