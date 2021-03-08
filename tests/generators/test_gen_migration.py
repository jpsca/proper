from freezegun import freeze_time

from proper.generators import gen_migration


def test_gen_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(app, "something blue")

    file = migrations / "2012_01_14_032134_something_blue.py"
    assert file.exists()

    content = file.read_text()
    assert "class SomethingBlue(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
