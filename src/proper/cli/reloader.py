"""Restarts the server when a file of the app changes.

Linux's inotify, called in libc with `ctypes`: no package to install, and
nothing compiled against one version of Python. inotify watches
directories, not trees, so `Watcher` adds a watch for every directory
under the roots (except the ones of `IGNORED_DIRS`) and for every one
created later.

inotify hears nothing of a file written from Windows on a drive mounted
in WSL (`/mnt/c`), so on WSL `PollingWatcher` compares the modification
times of the files every second instead. `PROPER_RELOAD_POLLING` forces
one or the other.

`run_process` keeps a child process running the server and starts a new
one whenever the watcher reports a change.
"""
import ctypes
import errno as errnos
import multiprocessing
import os
import platform
import select
import signal
import struct
import threading
import time
import typing as t
from pathlib import Path


if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from multiprocessing.process import BaseProcess


# inotify(7) event bits
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000
IN_DONT_FOLLOW = 0x02000000
IN_EXCL_UNLINK = 0x04000000
IN_ISDIR = 0x40000000

# What counts as a change: a file written and closed, created, deleted or
# moved, or touched (`IN_ATTRIB`, a common way to force a restart). Not
# `IN_MODIFY`: an editor saves a file in many writes, the close is one.
EVENTS = (
    IN_ATTRIB | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE
    | IN_DELETE_SELF | IN_MOVE_SELF
)
WATCH_MASK = EVENTS | IN_ONLYDIR | IN_DONT_FOLLOW | IN_EXCL_UNLINK

# Directories not watched: their files are not the app's code.
IGNORED_DIRS = frozenset({
    ".git", ".hg", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".idea", ".vscode",
})
# Files whose changes are not reported: compiled Python and editor leftovers.
IGNORED_SUFFIXES = (".pyc", ".pyo", ".swp", ".swx", ".tmp", "~")
IGNORED_PREFIXES = (".#",)

# The header of a `struct inotify_event`: wd, mask, cookie, len (then the
# name, `len` bytes, zero-padded).
_EVENT = struct.Struct("iIII")
_READ_SIZE = 64 * 1024

# How long the watcher waits, after a change, for the ones that come with
# it (an editor saves, git checks out many files) before it reports them.
DEBOUNCE = 0.3
# How often the polling watcher compares the tree with what it saw.
POLL_INTERVAL = 1.0


_libc = ctypes.CDLL(None, use_errno=True)
_inotify_init1 = _libc.inotify_init1
_inotify_init1.argtypes = [ctypes.c_int]
_inotify_init1.restype = ctypes.c_int
_inotify_add_watch = _libc.inotify_add_watch
_inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
_inotify_add_watch.restype = ctypes.c_int


def _check(result: int, what: str) -> int:
    """Raise the `OSError` of a failed libc call."""
    if result < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"{what}: {os.strerror(errno)}")
    return result


def is_ignored_file(name: str) -> bool:
    return name.endswith(IGNORED_SUFFIXES) or name.startswith(IGNORED_PREFIXES)


class Watcher:
    """Watches the trees under `roots` and reports the paths that change.

    Use it as a context manager, or `close()` it: it holds a file descriptor.
    """

    def __init__(self, *roots: str | Path, ignored_dirs: "Iterable[str]" = IGNORED_DIRS):
        self.roots = [Path(root).resolve() for root in roots]
        self.ignored_dirs = frozenset(ignored_dirs)
        self._dirs: dict[int, Path] = {}  # watch descriptor -> directory
        self.fd = _check(_inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC), "inotify_init1")
        try:
            for root in self.roots:
                self._watch_tree(root)
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "Watcher":
        return self

    def __exit__(self, *exc: t.Any) -> None:
        self.close()

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    @property
    def watched(self) -> set[Path]:
        return set(self._dirs.values())

    def _watch_tree(self, root: Path) -> None:
        """Watch `root` and every directory under it, except the ignored
        ones and symbolic links (`IN_DONT_FOLLOW` refuses those)."""
        self._watch(root)
        try:
            entries = list(os.scandir(root))
        except OSError:  # gone or unreadable since: nothing under it, then
            return
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and entry.name not in self.ignored_dirs:
                self._watch_tree(Path(entry.path))

    def _watch(self, directory: Path) -> None:
        wd = _inotify_add_watch(self.fd, bytes(directory), WATCH_MASK)
        if wd < 0:
            errno = ctypes.get_errno()
            # the directory went away, or is a symlink or unreadable: skip it
            if errno in (errnos.ENOENT, errnos.EACCES, errnos.ENOTDIR):
                return
            if errno == errnos.ENOSPC:  # the inotify limit of the user
                raise OSError(
                    errno,
                    f"Cannot watch {directory}: the limit of inotify watches is "
                    "reached. Raise it with "
                    "`sudo sysctl fs.inotify.max_user_watches=524288`.",
                )
            raise OSError(errno, f"inotify_add_watch({directory}): {os.strerror(errno)}")
        self._dirs[wd] = directory

    def wait(self, timeout: float | None = None, *, extra_fds: "Iterable[int]" = ()) -> set[Path]:
        """Block until something changes, or `timeout` seconds pass, or one of
        `extra_fds` is readable. Return the changed paths (empty when none).

        After the first change, keeps collecting for `DEBOUNCE` seconds of
        quiet, so that the changes of one save or one checkout come together.
        """
        fds = [self.fd, *extra_fds]
        ready, _, _ = select.select(fds, [], [], timeout)
        if self.fd not in ready:
            return set()
        changes = self._read()
        while True:
            ready, _, _ = select.select([self.fd], [], [], DEBOUNCE)
            if not ready:
                return changes
            changes |= self._read()

    def _read(self) -> set[Path]:
        """Read and decode every event queued; follow the directories that
        appear and disappear."""
        try:
            data = os.read(self.fd, _READ_SIZE)
        except BlockingIOError:
            return set()
        return self._decode(data)

    def _decode(self, data: bytes) -> set[Path]:
        changes: set[Path] = set()
        offset = 0
        while offset < len(data):
            wd, mask, _cookie, length = _EVENT.unpack_from(data, offset)
            offset += _EVENT.size
            name = data[offset : offset + length].split(b"\0", 1)[0].decode(errors="replace")
            offset += length
            if mask & IN_Q_OVERFLOW:
                # the kernel dropped events: anything may have changed
                changes.update(self.roots)
                continue
            if mask & IN_IGNORED:
                self._dirs.pop(wd, None)
                continue
            directory = self._dirs.get(wd)
            if directory is None:
                continue
            if mask & (IN_DELETE_SELF | IN_MOVE_SELF):
                changes.add(directory)
                continue
            path = directory / name
            if mask & IN_ISDIR:
                if name in self.ignored_dirs:
                    continue
                if mask & (IN_CREATE | IN_MOVED_TO):
                    self._watch_tree(path)
            elif is_ignored_file(name):
                continue
            changes.add(path)
        return changes


class PollingWatcher:
    """Finds the changes under `roots` by reading the modification times of
    every file, every `interval` seconds. Slower to notice and costlier
    than `Watcher`, but it sees what inotify cannot: a write made from
    Windows to a drive mounted in WSL.

    Same interface as `Watcher`; nothing to close.
    """

    fd = -1

    def __init__(
        self,
        *roots: str | Path,
        ignored_dirs: "Iterable[str]" = IGNORED_DIRS,
        interval: float | None = None,
    ):
        self.roots = [Path(root).resolve() for root in roots]
        self.ignored_dirs = frozenset(ignored_dirs)
        self.interval = POLL_INTERVAL if interval is None else interval
        self._seen = self._scan()

    def __enter__(self) -> "PollingWatcher":
        return self

    def __exit__(self, *exc: t.Any) -> None:
        self.close()

    def close(self) -> None:
        pass

    def _scan(self) -> dict[Path, int]:
        """The modification time of every file under the roots, in
        nanoseconds; the directories too, with -1, so that a new one is a
        change like it is for `Watcher`."""
        seen: dict[Path, int] = {}
        pending = list(self.roots)
        while pending:
            directory = pending.pop()
            seen[directory] = -1
            try:
                entries = list(os.scandir(directory))
            except OSError:  # gone or unreadable: nothing under it, then
                continue
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    if entry.name not in self.ignored_dirs:
                        pending.append(Path(entry.path))
                elif not is_ignored_file(entry.name):
                    try:
                        seen[Path(entry.path)] = entry.stat().st_mtime_ns
                    except OSError:  # deleted between the listing and the stat
                        pass
        return seen

    def _changes(self) -> set[Path]:
        """Compare the tree with the last scan, and keep the new one."""
        now = self._scan()
        before = self._seen
        self._seen = now
        return {
            path for path in before.keys() | now.keys()
            if before.get(path) != now.get(path)
        }

    def wait(self, timeout: float | None = None, *, extra_fds: "Iterable[int]" = ()) -> set[Path]:
        """Block until something changes, or `timeout` seconds pass, or one of
        `extra_fds` is readable. Return the changed paths (empty when none).

        After the first change, scans once more after `DEBOUNCE` seconds, so
        that the changes of one save or one checkout come together.
        """
        fds = list(extra_fds)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            step = self.interval
            if deadline is not None:
                step = min(step, max(0.0, deadline - time.monotonic()))
            ready, _, _ = select.select(fds, [], [], step)
            if ready:
                return set()
            changes = self._changes()
            if changes:
                time.sleep(DEBOUNCE)
                return changes | self._changes()
            if deadline is not None and time.monotonic() >= deadline:
                return set()


def is_wsl() -> bool:
    """Whether this Linux is the Windows Subsystem for Linux (its kernel
    release says "microsoft")."""
    uname = platform.uname()
    return uname.system.lower() == "linux" and "microsoft" in uname.release.lower()


def polling_wanted() -> bool:
    """`PROPER_RELOAD_POLLING` decides; unset, polling is for WSL only."""
    value = os.environ.get("PROPER_RELOAD_POLLING", "").strip().lower()
    if value:
        return value not in ("0", "false", "no", "off")
    return is_wsl()


def make_watcher(*roots: str | Path) -> "Watcher | PollingWatcher":
    if polling_wanted():
        return PollingWatcher(*roots)
    return Watcher(*roots)


def _relative(path: Path, roots: list[Path]) -> str:
    for root in roots:
        if path == root or root in path.parents:
            return str(path.relative_to(root)) or "."
    return str(path)


def run_process(
    path: str | Path,
    target: "Callable",
    kwargs: dict | None = None,
    callback: "Callable[[set[str]], None] | None" = None,
    *,
    grace: float = 10,
) -> int:
    """Run `target(**kwargs)` in a child process, and start a new one
    whenever a file under `path` changes. `callback` gets the changed paths,
    relative to `path`, before each restart.

    Returns when the child exits on its own with 0 (it was asked to stop),
    or when this process gets SIGINT or SIGTERM; the child is stopped
    first: SIGTERM, and SIGKILL after `grace` seconds. Returns the exit
    code of the last child.

    A child that dies (an import error, say) is not restarted until a
    file changes: the error stays on the screen, the fix restarts it.
    """
    ctx = multiprocessing.get_context("spawn")
    kwargs = kwargs or {}

    def on_term(signum: int, frame: t.Any) -> None:
        raise KeyboardInterrupt

    # only the main thread can: `proper run` is there, the tests are not
    in_main_thread = threading.current_thread() is threading.main_thread()
    previous = signal.signal(signal.SIGTERM, on_term) if in_main_thread else None
    process = ctx.Process(target=target, kwargs=kwargs)
    process.start()
    try:
        with make_watcher(path) as watcher:
            if isinstance(watcher, PollingWatcher):
                print(
                    "Watching for changes by polling, every "
                    f"{watcher.interval:g}s (PROPER_RELOAD_POLLING).",
                    flush=True,
                )
            while True:
                changes = watcher.wait(extra_fds=[process.sentinel] if process.is_alive() else [])
                if not changes:
                    # the child ended; stopped on purpose, or crashed
                    process.join()
                    if process.exitcode == 0:
                        return 0
                    print(
                        f"The server stopped with exit code {process.exitcode}. "
                        "Waiting for a change to start it again.",
                        flush=True,
                    )
                    changes = watcher.wait()
                if callback is not None:
                    callback({_relative(change, watcher.roots) for change in changes})
                _stop(process, grace)
                process = ctx.Process(target=target, kwargs=kwargs)
                process.start()
    except KeyboardInterrupt:
        pass
    finally:
        _stop(process, grace)
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    return process.exitcode or 0


def _stop(process: "BaseProcess", grace: float) -> None:
    if not process.is_alive():
        process.join()
        return
    process.terminate()
    process.join(grace)
    if process.is_alive():
        process.kill()
        process.join()
