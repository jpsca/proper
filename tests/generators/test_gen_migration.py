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


# def test_fields(app, scaffold):
#     app_root = scaffold
#     app.root_path = app_root
#     gen_model(
#         app,
#         "Product",
#         "name:string-30",
#         "description",
#         "price:numeric-10-2",
#         "data:json",
#     )

#     model_text = (app_root / "models" / "product.py").read_text()
#     assert "name = db.Column(db.String(30))" in model_text
#     assert "description = db.Column(db.String)" in model_text
#     assert "price = db.Column(db.Numeric(10, 2))" in model_text
#     assert "data = db.Column(db.JSON)" in model_text


# def test_constraints(app, scaffold):
#     app_root = scaffold
#     app.root_path = app_root
#     gen_model(
#         app, "Post", "slug:string:unique:index", "author_id:integer:foreign-users.id"
#     )

#     model_text = (app_root / "models" / "post.py").read_text()
#     assert "slug = db.Column(db.String, unique=True, index=True)" in model_text
#     assert 'author_id = db.Column(db.Integer, db.ForeignKey("users.id"))' in model_text

