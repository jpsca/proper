import sys

import pytest

from proper.seeds import run_seeds


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _isolate_db_modules():
    """Clear cached `db.*` modules between tests.

    Each test materializes a fresh `db/seeds/` package on disk; without
    cleanup, `importlib` would return the prior test's module from
    `sys.modules`.
    """
    yield
    for key in list(sys.modules):
        if key == "db" or key.startswith("db."):
            sys.modules.pop(key, None)


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """A clean project root with `db/` ready to be populated."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path


def _write_seed(
    path,
    name,
    *,
    envs=("dev", "test", "prod"),
    body="    pass",
):
    """Write a seed file. The seed appends its name to `_log` on the calling
    package so the test can verify run order."""
    seed_text = (
        "from . import _log\n\n"
        f"envs = {envs!r}\n\n\n"
        "def seed():\n"
        f"    _log.entries.append({name!r})\n"
        f"{body}\n"
    )
    (path / f"{name}.py").write_text(seed_text)


def _make_seeds_pkg(root, *, db=None):
    """Create either `db/seeds/` (db=None) or `db/seeds/<db>/`."""
    parts = ["db", "seeds"]
    if db:
        parts.append(db)
    pkg_path = root.joinpath(*parts)
    pkg_path.mkdir(parents=True)
    # Top-level `db/` and `db/seeds/` need to be importable packages too.
    (root / "db" / "__init__.py").write_text("")
    if db:
        (root / "db" / "seeds" / "__init__.py").write_text("")
    return pkg_path


# --- Discovery ---


class TestDiscovery:
    def test_no_seeds_package_returns_false(self, project, capsys):
        assert run_seeds() is False
        out = capsys.readouterr().out
        assert "No seeds defined" in out

    def test_empty_init_reports_no_seeds(self, project, capsys):
        pkg = _make_seeds_pkg(project)
        (pkg / "__init__.py").write_text("")
        result = run_seeds()
        assert result is True
        assert "No seeds registered" in capsys.readouterr().out

    def test_per_db_layout_takes_precedence(self, project, monkeypatch):
        """When both `db/seeds/__init__.py` and `db/seeds/main/__init__.py`
        exist, the per-database directory wins."""
        monkeypatch.setenv("APP_ENV", "dev")

        flat = _make_seeds_pkg(project)
        (flat / "__init__.py").write_text("from . import flat_seed  # noqa\n")
        (flat / "_log.py").write_text("entries = []\n")
        _write_seed(flat, "flat_seed")

        nested = _make_seeds_pkg(project, db="main")
        (nested / "__init__.py").write_text("from . import nested_seed  # noqa\n")
        (nested / "_log.py").write_text("entries = []\n")
        _write_seed(nested, "nested_seed")

        run_seeds(db="main")

        from db.seeds.main import _log as nested_log

        assert nested_log.entries == ["nested_seed"]


# --- Order, envs, single-name filter ---


class TestRun:
    def _setup_pkg(self, project, *, init_lines):
        pkg = _make_seeds_pkg(project)
        (pkg / "__init__.py").write_text("\n".join(init_lines) + "\n")
        (pkg / "_log.py").write_text("entries = []\n")
        return pkg

    def test_runs_in_import_order(self, project, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev")
        pkg = self._setup_pkg(
            project,
            init_lines=[
                "from . import roles  # noqa",
                "from . import admin_user  # noqa",
            ],
        )
        _write_seed(pkg, "roles")
        _write_seed(pkg, "admin_user")

        run_seeds()

        from db.seeds import _log

        assert _log.entries == ["roles", "admin_user"]

    def test_skips_when_env_not_in_envs(self, project, monkeypatch, capsys):
        monkeypatch.setenv("APP_ENV", "prod")
        pkg = self._setup_pkg(
            project,
            init_lines=["from . import sample  # noqa"],
        )
        _write_seed(pkg, "sample", envs=("dev",))

        run_seeds()

        from db.seeds import _log

        assert _log.entries == []
        out = capsys.readouterr().out
        assert "skipped" in out
        assert "APP_ENV='prod'" in out

    def test_runs_only_named_seed(self, project, monkeypatch):
        monkeypatch.setenv("APP_ENV", "dev")
        pkg = self._setup_pkg(
            project,
            init_lines=[
                "from . import roles  # noqa",
                "from . import admin_user  # noqa",
            ],
        )
        _write_seed(pkg, "roles")
        _write_seed(pkg, "admin_user")

        run_seeds(name="admin_user")

        from db.seeds import _log

        assert _log.entries == ["admin_user"]

    def test_named_seed_still_honors_envs(self, project, monkeypatch):
        """No --force: even single-name invocation respects envs."""
        monkeypatch.setenv("APP_ENV", "prod")
        pkg = self._setup_pkg(
            project,
            init_lines=["from . import dev_only  # noqa"],
        )
        _write_seed(pkg, "dev_only", envs=("dev",))

        run_seeds(name="dev_only")

        from db.seeds import _log

        assert _log.entries == []

    def test_unknown_seed_name_returns_false(self, project, monkeypatch, capsys):
        monkeypatch.setenv("APP_ENV", "dev")
        pkg = self._setup_pkg(
            project,
            init_lines=["from . import roles  # noqa"],
        )
        _write_seed(pkg, "roles")

        result = run_seeds(name="nope")

        assert result is False
        assert "not found" in capsys.readouterr().out

    def test_default_app_env_is_dev(self, project, monkeypatch):
        """If APP_ENV is unset the runner falls back to "dev"."""
        monkeypatch.delenv("APP_ENV", raising=False)
        pkg = self._setup_pkg(
            project,
            init_lines=["from . import only_dev  # noqa"],
        )
        _write_seed(pkg, "only_dev", envs=("dev",))

        run_seeds()

        from db.seeds import _log

        assert _log.entries == ["only_dev"]
