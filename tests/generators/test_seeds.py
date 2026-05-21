import pytest

from proper.generators.seed import gen_seed


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary project root.

    Mirrors the model-generator fixture: an app whose `root_path` points at
    `<tmp>/myapp/`, so `app.root_path.parent` is the project root and
    `db/seeds/` lives next to (a future) `myapp/`.
    """
    app_root = tmp_path / APP_NAME
    app_root.mkdir(parents=True)
    app.root_path = app_root
    app.name = APP_NAME
    return app


def _read(path):
    return path.read_text() if path.exists() else ""


# ---------------------------------------------------------------------------
# gen_seed - flat layout (default db == "main")
# ---------------------------------------------------------------------------


class TestGenSeedFlatLayout:
    def test_creates_seed_file(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        seed_path = tmp_path / "db" / "seeds" / "roles.py"
        assert seed_path.exists()
        text = seed_path.read_text()
        assert "def seed():" in text
        assert 'envs = ("dev", "test", "prod")' in text

    def test_creates_init_file(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        init_path = tmp_path / "db" / "seeds" / "__init__.py"
        assert init_path.exists()
        assert "from . import roles  # noqa" in init_path.read_text()

    def test_appends_to_existing_init(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        gen_seed(app_in_tmp, "admin_user")
        init_text = (tmp_path / "db" / "seeds" / "__init__.py").read_text()
        # Order is preserved - roles imported before admin_user.
        roles_idx = init_text.index("from . import roles")
        admin_idx = init_text.index("from . import admin_user")
        assert roles_idx < admin_idx

    def test_register_is_idempotent(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        gen_seed(app_in_tmp, "roles")
        init_text = (tmp_path / "db" / "seeds" / "__init__.py").read_text()
        # Exactly one import line.
        assert init_text.count("from . import roles  # noqa") == 1

    def test_does_not_overwrite_existing_seed(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        seed_path = tmp_path / "db" / "seeds" / "roles.py"
        seed_path.write_text("# user-edited content\n")
        gen_seed(app_in_tmp, "roles")
        assert seed_path.read_text() == "# user-edited content\n"

    def test_name_is_snake_cased(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "AdminUser")
        assert (tmp_path / "db" / "seeds" / "admin_user.py").exists()


# ---------------------------------------------------------------------------
# gen_seed - per-database layout (--db != "main")
# ---------------------------------------------------------------------------


class TestGenSeedNonDefaultDb:
    def test_creates_under_per_db_dir(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "reference_paths", db="analytics")
        seed_path = tmp_path / "db" / "seeds" / "analytics" / "reference_paths.py"
        assert seed_path.exists()

    def test_creates_per_db_init(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "reference_paths", db="analytics")
        init_path = tmp_path / "db" / "seeds" / "analytics" / "__init__.py"
        assert init_path.exists()
        assert "from . import reference_paths  # noqa" in init_path.read_text()

    def test_databases_do_not_collide(self, app_in_tmp, tmp_path):
        gen_seed(app_in_tmp, "roles")
        gen_seed(app_in_tmp, "page_view", db="analytics")

        assert (tmp_path / "db" / "seeds" / "roles.py").exists()
        assert (tmp_path / "db" / "seeds" / "analytics" / "page_view.py").exists()

        flat_init = _read(tmp_path / "db" / "seeds" / "__init__.py")
        analytics_init = _read(
            tmp_path / "db" / "seeds" / "analytics" / "__init__.py"
        )
        assert "roles" in flat_init
        assert "roles" not in analytics_init
        assert "page_view" in analytics_init
        assert "page_view" not in flat_init
