import pytest

from proper.generators import resource


@pytest.mark.skip(reason="Needs investigation")
def test_gen_resource(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    resource.gen_resource(app, "Product")

    product_text = (app_root / "controllers" / "product.py").read_text()
    print(product_text)
    assert """@router.resource("product")\nclass ProductController(BaseController):""" in product_text
    assert "def index(self):" in product_text
    assert "def new(self):" in product_text
    assert "def create(self):" in product_text
    assert "def show(self):" in product_text
    assert "def edit(self):" in product_text
    assert "def update(self):" in product_text
    assert "def delete(self):" in product_text

    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(BaseModel):" in model_text

    views = app_root / "views" / "product"
    assert views.is_dir()
    assert (views / "index.jinja").exists()
    assert (views / "new.jinja").exists()
    assert (views / "show.jinja").exists()
    assert (views / "edit.jinja").exists()


@pytest.mark.skip(reason="Needs investigation")
def test_gen_resource_singular(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    resource.gen_resource(app, "Profile", singular=True)

    product_text = (app_root / "controllers" / "profile.py").read_text()
    assert "class ProfileController(BaseController):" in product_text
    assert "def index(self):" not in product_text
    assert "def new(self):" in product_text
    assert "def create(self):" in product_text
    assert "def show(self):" in product_text
    assert "def edit(self):" in product_text
    assert "def update(self):" in product_text
    assert "def delete(self):" in product_text

    model_text = (app_root / "models" / "profile.py").read_text()
    assert "class Profile(BaseModel):" in model_text

    views = app_root / "views" / "profile"
    assert views.is_dir()
    assert not (views / "index.jinja").exists()
    assert (views / "new.jinja").exists()
    assert (views / "show.jinja").exists()
    assert (views / "edit.jinja").exists()


