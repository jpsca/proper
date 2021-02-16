from proper.generators import gen_model


def test_base_model(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(app, "Product")

    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(Base, Timestamped):" in model_text
    assert '__tablename__ = "products"' in model_text
    assert "id = db.Column(db.Integer, primary_key=True)" in model_text

    init_text = (app_root / "models" / "__init__.py").read_text()
    assert init_text.strip() == "from .product import *  # noqa"


def test_fields(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(
        app,
        "Product",
        "name:string-30",
        "description",
        "price:numeric-10-2",
        "data:json",
    )

    model_text = (app_root / "models" / "product.py").read_text()
    assert "name = db.Column(db.String(30))" in model_text
    assert "description = db.Column(db.String)" in model_text
    assert "price = db.Column(db.Numeric(10, 2))" in model_text
    assert "data = db.Column(db.JSON)" in model_text


def test_constraints(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(
        app, "Post", "slug:string:unique:index", "author_id:integer:foreign-users.id"
    )

    model_text = (app_root / "models" / "post.py").read_text()
    assert "slug = db.Column(db.String, unique=True, index=True)" in model_text
    assert 'author_id = db.Column(db.Integer, db.ForeignKey("users.id"))' in model_text


def test_simple_backref(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(
        app, "Post", "tags:Tag:post:joined"
    )

    model_text = (app_root / "models" / "post.py").read_text()
    expected = 'tags = db.relationship("Tag", backref=db.backref("post"), lazy="joined")'
    assert expected in model_text


def test_backref_with_lazy(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(
        app, "Post", "tags:Tag:post-select:joined"
    )

    model_text = (app_root / "models" / "post.py").read_text()
    expected = 'tags = db.relationship("Tag", backref=db.backref("post", lazy="select"), lazy="joined")'
    assert expected in model_text


def test_implicit_backref_and_lazy(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(
        app, "Post", "tags:Tag"
    )

    model_text = (app_root / "models" / "post.py").read_text()
    expected = 'tags = db.relationship("Tag", backref=db.backref("posts"), lazy="select")'
    assert expected in model_text
