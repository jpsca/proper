import pytest

from proper.generators.resource import gen_resource


# --- Fixtures ---

APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with directories expected by both
    gen_model (models/) and gen_resource (controllers/, forms/, views/)."""
    app_root = tmp_path / APP_NAME
    for d in ("models", "controllers", "forms", "views"):
        (app_root / d).mkdir(parents=True)
    (app_root / "models" / "__init__.py").write_text("")
    (app_root / "controllers" / "__init__.py").write_text("")
    (app_root / "forms" / "__init__.py").write_text("")
    (app_root / "views" / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


# --- Helpers ---


def _init_text(app) -> str:
    return (app.root_path / "controllers" / "__init__.py").read_text()


def _controller_text(app, name_snake: str) -> str:
    return (app.root_path / "controllers" / f"{name_snake}_controller.py").read_text()


def _form_text(app, name_snake: str) -> str:
    return (app.root_path / "forms" / f"{name_snake}.py").read_text()


def _model_text(app, name_snake: str) -> str:
    return (app.root_path / "models" / f"{name_snake}.py").read_text()


def _views_folder(app, name_snake: str):
    return app.root_path / "views" / name_snake


# --- File generation ---


def test_generated_files(app_in_tmp):
    gen_resource(app_in_tmp, "Product")

    # appends_to_init
    init = _init_text(app_in_tmp)
    assert "product_controller" in init

    # creates_controller
    assert (app_in_tmp.root_path / "controllers" / "product_controller.py").exists()

    # creates_model
    assert (app_in_tmp.root_path / "models" / "product.py").exists()

    # creates_form
    assert (app_in_tmp.root_path / "forms" / "product.py").exists()

    # creates_views
    views = _views_folder(app_in_tmp, "product")
    assert (views / "index.jx").exists()
    assert (views / "new.jx").exists()
    assert (views / "show.jx").exists()
    assert (views / "edit.jx").exists()
    assert (views / "form.jx").exists()

    # class_definition
    text = _controller_text(app_in_tmp, "product")
    assert "class ProductController(AppController):" in text

    # resource_decorator
    text = _controller_text(app_in_tmp, "product")
    assert '@router.resource("products")' in text

    # all_default_actions
    text = _controller_text(app_in_tmp, "product")
    assert "def index(self):" in text
    assert "def show(self):" in text
    assert "def new(self):" in text
    assert "def edit(self):" in text
    assert "def create(self):" in text
    assert "def update(self):" in text
    assert "def delete(self):" in text

    # load_method
    text = _controller_text(app_in_tmp, "product")
    assert "def set_product(self):" in text

    # imports
    text = _controller_text(app_in_tmp, "product")
    assert "from myapp.models import Product" in text
    assert "from myapp.forms.product import ProductForm" in text
    assert "from myapp.router import router" in text


def test_generated_namespaced_files(app_in_tmp):
    gen_resource(app_in_tmp, "Product", namespace="admin")

    # appends_to_init
    init = _init_text(app_in_tmp)
    assert "admin" in init
    assert "product_controller" in init

    # creates_controller
    assert (app_in_tmp.root_path / "controllers" / "admin" / "__init__.py").exists()
    assert (app_in_tmp.root_path / "controllers" / "admin" / "product_controller.py").exists()

    # creates_model
    assert (app_in_tmp.root_path / "models" / "product.py").exists()

    # creates_form
    assert (app_in_tmp.root_path / "forms" / "admin" / "__init__.py").exists()
    assert (app_in_tmp.root_path / "forms" / "admin"/ "product.py").exists()

    # creates_views
    views = _views_folder(app_in_tmp, "admin/product")
    assert (views / "index.jx").exists()
    assert (views / "new.jx").exists()
    assert (views / "show.jx").exists()
    assert (views / "edit.jx").exists()
    assert (views / "form.jx").exists()


# --- Model content ---


class TestModel:
    def test_model_with_attrs(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", "title:str", "price:float")
        text = _model_text(app_in_tmp, "product")
        assert "class Product(BaseModel):" in text
        assert "title = pw.CharField()" in text
        assert "price = pw.FloatField()" in text

    def test_model_default_row_when_no_attrs(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product")
        text = _model_text(app_in_tmp, "product")
        assert "name = pw.CharField()" in text


# --- Form content ---


class TestForm:
    def test_form_class(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", "title:str", "price:float")
        text = _form_text(app_in_tmp, "product")
        assert "class ProductForm(f.Form):" in text
        assert "orm_cls = Product" in text

    def test_form_fields(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", "title:str", "price:float", "active:bool")
        text = _form_text(app_in_tmp, "product")
        assert "title = f.TextField()" in text
        assert "price = f.FloatField()" in text
        assert "active = f.BooleanField()" in text

    def test_foreign_key_excluded_from_form(self, app_in_tmp):
        gen_resource(app_in_tmp, "Tweet", "body:text", "user:fk-User")
        text = _form_text(app_in_tmp, "tweet")
        assert "body = f.TextField()" in text
        # fk types are not in FORM_FIELDS, so they are excluded
        assert "user" not in text


# --- Singular resources ---


class TestSingular:
    def test_singular_removes_index(self, app_in_tmp):
        gen_resource(app_in_tmp, "Profile", singular=True)
        text = _controller_text(app_in_tmp, "profile")
        assert "def index(self):" not in text
        assert "def show(self):" in text
        assert "def new(self):" in text
        assert "def create(self):" in text

    def test_singular_no_index_view(self, app_in_tmp):
        gen_resource(app_in_tmp, "Profile", singular=True)
        views = _views_folder(app_in_tmp, "profile")
        assert not (views / "index.jx").exists()
        assert (views / "show.jx").exists()

    def test_singular_pk_none(self, app_in_tmp):
        gen_resource(app_in_tmp, "Profile", singular=True)
        text = _controller_text(app_in_tmp, "profile")
        assert "pk=None" in text


# --- only / exclude filtering ---


class TestActionFiltering:
    def test_only_limits_actions(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", only="index,show")
        text = _controller_text(app_in_tmp, "product")
        assert "def index(self):" in text
        assert "def show(self):" in text
        assert "def new(self):" not in text
        assert "def create(self):" not in text
        assert "def edit(self):" not in text
        assert "def update(self):" not in text
        assert "def delete(self):" not in text

    def test_only_limits_views(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", only="index,show")
        views = _views_folder(app_in_tmp, "product")
        assert (views / "index.jx").exists()
        assert (views / "show.jx").exists()
        assert not (views / "new.jx").exists()
        assert not (views / "edit.jx").exists()

    def test_exclude_removes_actions(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", exclude="delete,edit,update")
        text = _controller_text(app_in_tmp, "product")
        assert "def index(self):" in text
        assert "def show(self):" in text
        assert "def new(self):" in text
        assert "def create(self):" in text
        assert "def edit(self):" not in text
        assert "def update(self):" not in text
        assert "def delete(self):" not in text

    def test_exclude_removes_views(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", exclude="index,new,edit")
        views = _views_folder(app_in_tmp, "product")
        assert not (views / "index.jx").exists()
        assert not (views / "new.jx").exists()
        assert not (views / "edit.jx").exists()
        assert (views / "show.jx").exists()


# --- Custom pk ---


class TestCustomPk:
    def test_pk_in_decorator(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", pk="slug")
        text = _controller_text(app_in_tmp, "product")
        assert 'pk="slug"' in text

    def test_pk_strips_colon(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", pk=":slug:")
        text = _controller_text(app_in_tmp, "product")
        assert 'pk="slug"' in text


# --- Name inflection ---


class TestNameInflection:
    def test_snake_case_name(self, app_in_tmp):
        gen_resource(app_in_tmp, "blog_post")
        text = _controller_text(app_in_tmp, "blog_post")
        assert "class BlogPostController(AppController):" in text
        assert '@router.resource("blog_posts")' in text

    def test_model_inflected(self, app_in_tmp):
        gen_resource(app_in_tmp, "blog_post")
        text = _model_text(app_in_tmp, "blog_post")
        assert "class BlogPost(BaseModel):" in text


# --- Migration ---


class TestMigration:
    def test_no_migration_by_default(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product")
        # Files generated without invoking migration
        assert (app_in_tmp.root_path / "controllers" / "product_controller.py").exists()
        assert (app_in_tmp.root_path / "models" / "product.py").exists()

    def test_migration_still_generates_files(self, app_in_tmp):
        gen_resource(app_in_tmp, "Product", migration=True)
        # Files are generated even when migration=True
        assert (app_in_tmp.root_path / "controllers" / "product_controller.py").exists()
        assert (app_in_tmp.root_path / "models" / "product.py").exists()
        text = _controller_text(app_in_tmp, "product")
        assert "class ProductController(AppController):" in text
