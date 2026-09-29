"""Shared bits of the micro-benchmarks: a timer that reports the best of a
few runs, so a busy machine adds noise upwards only."""
import time


def best_of(fn, *, runs: int = 5, count: int = 20000) -> float:
    """Microseconds per call of `fn`, best of `runs` batches of `count`."""
    best = float("inf")
    for _ in range(runs):
        started = time.perf_counter()
        for _ in range(count):
            fn()
        best = min(best, (time.perf_counter() - started) / count * 1e6)
    return best


def once(fn) -> float:
    """Milliseconds of one call of `fn`."""
    started = time.perf_counter()
    fn()
    return (time.perf_counter() - started) * 1e3
