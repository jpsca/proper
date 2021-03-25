from freezegun import freeze_time

from proper.generators import gen_migration


def test_empty_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(app, "something blue")

    content = (migrations / "2012_01_14_032134_something_blue.py").read_text()
    assert "class SomethingBlue(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content


def test_update_table(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(app, "meh", table="products")

    content = (migrations / "2012_01_14_032134_meh.py").read_text()
    print(content)
    assert "class Meh(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
    assert 'self.schema.create("products") as table:' not in content
    assert 'self.schema.table("products") as table:' in content


def test_create_table(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(app, "meh", table="products", create=True)

    content = (migrations / "2012_01_14_032134_meh.py").read_text()
    print(content)
    assert "class Meh(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
    assert 'self.schema.create("products") as table:' in content
    assert 'table.increments("id")' in content
    assert "table.timestamps()" in content


def test_add_columns(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(
            app,
            "meh",
            "name:string-30",
            "description",
            "price:decimal-10-2",
            "data:json",
            table="products",
            create=True,
        )

    content = (migrations / "2012_01_14_032134_meh.py").read_text()
    print(content)
    assert 'table.increments("id")' in content
    assert "table.timestamps()" in content
    assert 'table.string("name", 30)' in content
    assert 'table.string("description")' in content
    assert 'table.decimal("price", 10, 2)' in content
    assert 'table.json("data")' in content


def test_add_constraints(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    migrations = (app_root / ".." / "db" / "migrations").resolve()

    with freeze_time("2012-01-14 03:21:34"):
        gen_migration(
            app,
            "meh",
            "created_by:string:default-api",
            "slug:string:unique:index",
            "description:string:nullable",
            "author_id:integer:foreign-users.id",
            table="products",
            create=True,
        )

    content = (migrations / "2012_01_14_032134_meh.py").read_text()
    print(content)
    assert 'table.string("created_by").default("api")' in content
    assert 'table.string("slug").unique().index()' in content
    assert 'table.string("description").nullable()' in content
    assert 'table.integer("author_id").unsigned()' in content
    assert 'table.foreign("author_id").references("id").on("users")' in content
