"""The reloader of `proper run`: what it watches, and how it restarts."""
import errno
import multiprocessing
import os
import signal
import struct
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from proper.cli import reloader
from proper.cli.reloader import (
    IN_CREATE,
    IN_DELETE_SELF,
    IN_IGNORED,
    IN_ISDIR,
    IN_Q_OVERFLOW,
    PollingWatcher,
    Watcher,
    is_ignored_file,
    make_watcher,
    run_process,
)


def settle(watcher: Watcher) -> None:
    """Drain the events of setting things up."""
    while watcher.wait(timeout=0.05):
        pass


def event(wd: int, mask: int, name: bytes = b"") -> bytes:
    padded = name + b"\0" * (4 - len(name) % 4) if name else b""
    return struct.pack("iIII", wd, mask, 0, len(padded)) + padded


class TestWatcher:
    def test_watches_the_tree_except_the_ignored_dirs(self, tmp_path):
        (tmp_path / "app" / "views").mkdir(parents=True)
        (tmp_path / "app" / "__pycache__").mkdir()
        (tmp_path / ".git" / "objects").mkdir(parents=True)
        (tmp_path / "node_modules").mkdir()
        os.symlink(tmp_path / "app", tmp_path / "link")

        with Watcher(tmp_path) as watcher:
            assert watcher.watched == {tmp_path, tmp_path / "app", tmp_path / "app" / "views"}

    def test_a_written_file_is_a_change(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (tmp_path / "a.py").write_text("x = 1")
            assert watcher.wait(timeout=2) == {tmp_path / "a.py"}

    def test_a_touched_file_is_a_change(self, tmp_path):
        target = tmp_path / "a.py"
        target.write_text("")
        with Watcher(tmp_path) as watcher:
            os.utime(target)
            assert watcher.wait(timeout=2) == {target}

    def test_a_new_directory_is_watched_too(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (tmp_path / "new").mkdir()
            assert watcher.wait(timeout=2) == {tmp_path / "new"}
            (tmp_path / "new" / "b.py").write_text("")
            assert watcher.wait(timeout=2) == {tmp_path / "new" / "b.py"}

    def test_a_new_ignored_directory_is_not_watched(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (tmp_path / "__pycache__").mkdir()
            (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"")
            assert watcher.wait(timeout=2) == set()
            assert tmp_path / "__pycache__" not in watcher.watched

    def test_editor_leftovers_are_not_changes(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (tmp_path / "a.py~").write_text("")
            (tmp_path / ".a.py.swp").write_text("")
            (tmp_path / ".#a.py").write_text("")
            (tmp_path / "a.pyc").write_bytes(b"")
            assert watcher.wait(timeout=1) == set()

    def test_a_removed_directory_is_a_change_and_is_forgotten(self, tmp_path):
        (tmp_path / "gone").mkdir()
        with Watcher(tmp_path) as watcher:
            (tmp_path / "gone").rmdir()
            assert tmp_path / "gone" in watcher.wait(timeout=2)
            settle(watcher)
            assert watcher.watched == {tmp_path}

    def test_a_moved_in_directory_is_watched(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "root"
        root.mkdir()
        with Watcher(root) as watcher:
            outside.rename(root / "inside")
            assert watcher.wait(timeout=2) == {root / "inside"}
            (root / "inside" / "c.py").write_text("")
            assert watcher.wait(timeout=2) == {root / "inside" / "c.py"}

    def test_changes_of_one_burst_come_together(self, tmp_path):
        with Watcher(tmp_path) as watcher:

            def write_many():
                for i in range(3):
                    (tmp_path / f"{i}.py").write_text("")
                    time.sleep(0.05)

            thread = threading.Thread(target=write_many)
            thread.start()
            changes = watcher.wait(timeout=2)
            thread.join()
        assert changes == {tmp_path / f"{i}.py" for i in range(3)}

    def test_nothing_within_the_timeout(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            assert watcher.wait(timeout=0.05) == set()

    def test_an_extra_fd_ends_the_wait(self, tmp_path):
        read_end, write_end = os.pipe()
        try:
            with Watcher(tmp_path) as watcher:
                os.write(write_end, b"x")
                assert watcher.wait(timeout=2, extra_fds=[read_end]) == set()
        finally:
            os.close(read_end)
            os.close(write_end)

    def test_close_is_idempotent(self, tmp_path):
        watcher = Watcher(tmp_path)
        watcher.close()
        watcher.close()
        assert watcher.fd == -1

    def test_a_read_with_nothing_queued(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            assert watcher._read() == set()

    def test_an_overflow_reports_the_roots(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            assert watcher._decode(event(-1, IN_Q_OVERFLOW)) == {tmp_path}

    def test_an_ignored_descriptor_is_forgotten(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (wd,) = watcher._dirs
            assert watcher._decode(event(wd, IN_IGNORED)) == set()
            assert watcher.watched == set()

    def test_an_unknown_descriptor_is_skipped(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            assert watcher._decode(event(999, IN_CREATE, b"x.py")) == set()

    def test_the_root_removed_is_a_change(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (wd,) = watcher._dirs
            assert watcher._decode(event(wd, IN_DELETE_SELF)) == {tmp_path}

    def test_a_directory_that_vanishes_while_scanning_is_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "sub").mkdir()
        real_scandir = os.scandir

        def scandir(path):
            if Path(path) == tmp_path / "sub":
                raise FileNotFoundError(path)
            return real_scandir(path)

        monkeypatch.setattr(os, "scandir", scandir)
        with Watcher(tmp_path) as watcher:
            assert watcher.watched == {tmp_path, tmp_path / "sub"}

    def test_a_directory_gone_before_the_watch_is_skipped(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            watcher._watch(tmp_path / "missing")
            assert watcher.watched == {tmp_path}

    def test_a_new_directory_renamed_to_an_ignored_name_is_skipped(self, tmp_path):
        with Watcher(tmp_path) as watcher:
            (wd,) = watcher._dirs
            assert watcher._decode(event(wd, IN_CREATE | IN_ISDIR, b".git")) == set()

    def test_the_watch_limit_has_a_hint(self, tmp_path, monkeypatch):
        def add_watch(fd, path, mask):
            import ctypes

            ctypes.set_errno(errno.ENOSPC)
            return -1

        monkeypatch.setattr(reloader, "_inotify_add_watch", add_watch)
        with pytest.raises(OSError, match="max_user_watches"):
            Watcher(tmp_path)

    def test_another_watch_error_is_raised(self, tmp_path, monkeypatch):
        def add_watch(fd, path, mask):
            import ctypes

            ctypes.set_errno(errno.EBADF)
            return -1

        monkeypatch.setattr(reloader, "_inotify_add_watch", add_watch)
        with pytest.raises(OSError, match="inotify_add_watch"):
            Watcher(tmp_path)

    def test_init_failure_is_raised(self, monkeypatch):
        def init(flags):
            import ctypes

            ctypes.set_errno(errno.EMFILE)
            return -1

        monkeypatch.setattr(reloader, "_inotify_init1", init)
        with pytest.raises(OSError, match="inotify_init1"):
            Watcher("/")

    def test_ignored_files(self):
        assert is_ignored_file("a.pyc")
        assert is_ignored_file(".#a.py")
        assert not is_ignored_file("a.py")
        assert not is_ignored_file(".env")

    def test_relative_paths(self, tmp_path):
        roots = [tmp_path]
        assert reloader._relative(tmp_path / "a" / "b.py", roots) == "a/b.py"
        assert reloader._relative(tmp_path, roots) == "."
        assert reloader._relative(Path("/elsewhere/x"), roots) == "/elsewhere/x"


class TestPollingWatcher:
    def polling(self, *roots):
        return PollingWatcher(*roots, interval=0.05)

    def test_sees_the_tree_except_the_ignored_dirs(self, tmp_path):
        (tmp_path / "app" / "views").mkdir(parents=True)
        (tmp_path / "app" / "a.py").write_text("")
        (tmp_path / "app" / "__pycache__").mkdir()
        (tmp_path / "app" / "__pycache__" / "a.pyc").write_bytes(b"")
        (tmp_path / "app" / "b.pyc").write_bytes(b"")
        (tmp_path / ".git").mkdir()
        os.symlink(tmp_path / "app", tmp_path / "link")

        with self.polling(tmp_path) as watcher:
            assert set(watcher._seen) == {
                tmp_path, tmp_path / "app", tmp_path / "app" / "views", tmp_path / "app" / "a.py",
            }

    def test_a_written_file_is_a_change(self, tmp_path):
        target = tmp_path / "a.py"
        target.write_text("")
        with self.polling(tmp_path) as watcher:
            os.utime(target, ns=(0, 10**9))
            assert watcher.wait(timeout=2) == {target}

    def test_new_and_deleted_files_and_dirs_are_changes(self, tmp_path):
        old = tmp_path / "old.py"
        old.write_text("")
        with self.polling(tmp_path) as watcher:
            old.unlink()
            (tmp_path / "new").mkdir()
            (tmp_path / "new" / "b.py").write_text("")
            assert watcher.wait(timeout=2) == {old, tmp_path / "new", tmp_path / "new" / "b.py"}

    def test_leftovers_and_ignored_dirs_are_not_changes(self, tmp_path):
        with self.polling(tmp_path) as watcher:
            (tmp_path / "a.py~").write_text("")
            (tmp_path / "__pycache__").mkdir()
            assert watcher.wait(timeout=0.3) == set()

    def test_nothing_within_the_timeout(self, tmp_path):
        with self.polling(tmp_path) as watcher:
            assert watcher.wait(timeout=0.12) == set()

    def test_an_extra_fd_ends_the_wait(self, tmp_path):
        read_end, write_end = os.pipe()
        try:
            with self.polling(tmp_path) as watcher:
                os.write(write_end, b"x")
                assert watcher.wait(timeout=2, extra_fds=[read_end]) == set()
        finally:
            os.close(read_end)
            os.close(write_end)

    def test_a_directory_that_vanishes_while_scanning_is_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "sub").mkdir()
        real_scandir = os.scandir

        def scandir(path):
            if Path(path) == tmp_path / "sub":
                raise FileNotFoundError(path)
            return real_scandir(path)

        monkeypatch.setattr(os, "scandir", scandir)
        assert set(self.polling(tmp_path)._seen) == {tmp_path, tmp_path / "sub"}

    def test_a_file_deleted_between_listing_and_stat_is_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("")
        real_scandir = os.scandir

        class Entry:
            def __init__(self, entry):
                self._entry = entry
                self.name, self.path = entry.name, entry.path

            def is_symlink(self):
                return False

            def is_dir(self):
                return False

            def stat(self):
                raise FileNotFoundError(self.path)

        def scandir(path):
            return [Entry(entry) for entry in real_scandir(path)]

        monkeypatch.setattr(os, "scandir", scandir)
        assert set(self.polling(tmp_path)._seen) == {tmp_path}

    def test_the_roots_are_resolved(self, tmp_path):
        with self.polling(tmp_path / "." / "..") as watcher:
            assert watcher.roots == [tmp_path.parent]


class TestMakeWatcher:
    def test_linux_gets_inotify(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROPER_RELOAD_POLLING", raising=False)
        monkeypatch.setattr(reloader.platform, "uname", lambda: SimpleNamespace(system="Linux", release="6.1.0"))
        with make_watcher(tmp_path) as watcher:
            assert isinstance(watcher, Watcher)

    def test_wsl_gets_polling(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROPER_RELOAD_POLLING", raising=False)
        monkeypatch.setattr(
            reloader.platform,
            "uname",
            lambda: SimpleNamespace(system="Linux", release="5.15.167.4-microsoft-standard-WSL2"),
        )
        assert isinstance(make_watcher(tmp_path), PollingWatcher)

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
    def test_the_variable_forces_polling(self, tmp_path, monkeypatch, value):
        monkeypatch.setenv("PROPER_RELOAD_POLLING", value)
        assert isinstance(make_watcher(tmp_path), PollingWatcher)

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_the_variable_forces_inotify_even_on_wsl(self, tmp_path, monkeypatch, value):
        monkeypatch.setenv("PROPER_RELOAD_POLLING", value)
        monkeypatch.setattr(reloader, "is_wsl", lambda: True)
        with make_watcher(tmp_path) as watcher:
            assert isinstance(watcher, Watcher)


# --- run_process: the target must be importable by a spawned process


def server(root: str) -> None:
    """Stands in for the server. Writes its pid to `pids` next to `root` (not
    under it: that would be a change), then does what the flag files in
    `root` say: `crash` exits with 3, `quit` with 0, none of them waits to
    be stopped."""
    root_path = Path(root)
    with open(root_path.parent / "pids", "a") as f:
        f.write(f"{os.getpid()}\n")
    if (root_path / "crash").exists():
        raise SystemExit(3)
    if (root_path / "quit").exists():
        return
    time.sleep(60)


def stubborn(ready: str) -> None:
    """Ignores SIGTERM; says so in the file `ready`."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(ready).write_text("")
    time.sleep(60)


def wait_for_pids(root: Path, count: int, timeout: float = 10) -> list[int]:
    record = root.parent / "pids"
    deadline = time.monotonic() + timeout
    lines: list[str] = []
    while time.monotonic() < deadline:
        lines = record.read_text().splitlines() if record.exists() else []
        if len(lines) >= count:
            return [int(line) for line in lines]
        time.sleep(0.05)
    raise AssertionError(f"{record} has {len(lines)} lines, wanted {count}")


def alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def wait_until_gone(pid: int, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(pid)


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    return root


class Supervisor:
    """`run_process` in a thread, with the server stand-in as the target."""

    def __init__(self, root: Path, callback=None):
        self.root = root
        self.results: list[int] = []
        self.thread = threading.Thread(
            target=lambda: self.results.append(
                run_process(root, server, {"root": str(root)}, callback=callback)
            )
        )
        self.thread.start()

    def finish(self) -> int:
        """Ask the next child to quit: `run_process` ends with it."""
        (self.root / "quit").write_text("")
        self.thread.join(15)
        assert not self.thread.is_alive()
        return self.results[0]


class TestRunProcess:
    def test_a_change_restarts_the_child(self, root):
        seen = []
        supervisor = Supervisor(root, callback=seen.append)
        (first,) = wait_for_pids(root, 1)
        (root / "a.py").write_text("")
        _, second = wait_for_pids(root, 2)
        wait_until_gone(first)
        assert second != first
        assert seen[0] == {"a.py"}

        assert supervisor.finish() == 0
        wait_until_gone(second)

    def test_polling_restarts_the_child_too(self, root, monkeypatch, capsys):
        monkeypatch.setenv("PROPER_RELOAD_POLLING", "1")
        monkeypatch.setattr(reloader, "POLL_INTERVAL", 0.05)
        seen = []
        supervisor = Supervisor(root, callback=seen.append)
        (first,) = wait_for_pids(root, 1)
        (root / "a.py").write_text("")
        _, second = wait_for_pids(root, 2)
        wait_until_gone(first)
        assert second != first
        assert seen[0] == {"a.py"}
        assert "by polling" in capsys.readouterr().out

        assert supervisor.finish() == 0
        wait_until_gone(second)

    def test_a_crashed_child_waits_for_a_change(self, root, capsys):
        (root / "crash").write_text("")
        supervisor = Supervisor(root)
        wait_for_pids(root, 1)
        time.sleep(0.6)
        assert len(wait_for_pids(root, 1)) == 1  # not restarted by itself
        assert "exit code 3" in capsys.readouterr().out

        (root / "crash").unlink()
        wait_for_pids(root, 2)
        assert supervisor.finish() == 0

    def test_a_child_that_quits_cleanly_ends_the_reloader(self, root):
        (root / "quit").write_text("")
        supervisor = Supervisor(root)
        supervisor.thread.join(10)
        assert supervisor.results == [0]

    def test_sigterm_stops_the_child_and_returns(self, root):
        """In a process of our own: the handler needs the main thread."""
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(target=run_process, args=(str(root), server, {"root": str(root)}))
        process.start()
        try:
            (server_pid,) = wait_for_pids(root, 1)
            os.kill(process.pid, signal.SIGTERM)
            process.join(10)
            assert process.exitcode == 0
            wait_until_gone(server_pid)
        finally:
            if process.is_alive():
                process.kill()

    def test_a_stubborn_child_is_killed(self, tmp_path):
        ready = tmp_path / "ready"
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(target=stubborn, args=(str(ready),))
        process.start()
        for _ in range(200):
            if ready.exists():
                break
            time.sleep(0.05)
        assert ready.exists()
        reloader._stop(process, grace=0.2)
        assert not process.is_alive()
        assert process.exitcode == -signal.SIGKILL

    def test_stopping_a_finished_child_just_joins(self, root):
        (root / "quit").write_text("")
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(target=server, args=(str(root),))
        process.start()
        process.join()
        reloader._stop(process, grace=1)
        assert process.exitcode == 0
