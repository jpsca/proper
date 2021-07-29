from freezegun import freeze_time

from proper.generators import gen_resource


def test_gen_resource(app, scaffold):
    app_root = scaffold
    app.root_path = app_root

    with freeze_time("2012-01-14 03:21:34"):
        gen_resource(app, "Products")

    _test_controller(app_root)
    _test_model(app_root)
    _test_migration(app_root)
    _test_templates(app_root)
    _test_routes(app_root)


def _test_controller(app_root):
    products_text = (app_root / "controllers" / "products.py").read_text()
    assert "class Products(ApplicationController):" in products_text
    assert "def index(self, req, resp):" in products_text
    assert "def new(self, req, resp):" in products_text
    assert "def create(self, req, resp):" in products_text
    assert "def show(self, req, resp, uid):" in products_text
    assert "def edit(self, req, resp, uid):" in products_text
    assert "def update(self, req, resp, uid):" in products_text
    assert "def delete(self, req, resp, uid):" in products_text

    init_text = (app_root / "controllers" / "__init__.py").read_text()
    assert init_text.strip() == "from .products import *  # noqa"


def _test_model(app_root):
    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(Base):" in model_text

    init_text = (app_root / "models" / "__init__.py").read_text()
    assert init_text.strip() == "from .product import *  # noqa"


def _test_migration(app_root):
    migration = app_root / ".." / "db" / "migrations" / "2012_01_14_032134_create_products.py"
    assert migration.exists()

    content = migration.read_text()
    assert "class CreateProducts(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
    assert 'self.schema.create("products") as table:' in content


def _test_templates(app_root):
    templates = app_root / "templates" / "products"
    assert templates.is_dir()
    assert (templates / "index.html.jinja").exists()
    assert (templates / "new.html.jinja").exists()
    assert (templates / "show.html.jinja").exists()
    assert (templates / "edit.html.jinja").exists()


def _test_routes(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""routes = [
    get("", to=Pages.index),

    resource("products", to=Products),
]

""")


def test_gen_resource_singular(app, scaffold):
    app_root = scaffold
    app.root_path = app_root

    with freeze_time("2012-01-14 03:21:34"):
        gen_resource(app, "Profile", singular=True)

    _test_controller_singular(app_root)
    _test_model_singular(app_root)
    _test_migration_singular(app_root)
    _test_templates_singular(app_root)
    _test_routes_singular(app_root)


def _test_controller_singular(app_root):
    products_text = (app_root / "controllers" / "profile.py").read_text()
    assert "class Profile(ApplicationController):" in products_text
    assert "def index(self, req, resp):" not in products_text
    assert "def new(self, req, resp):" in products_text
    assert "def create(self, req, resp):" in products_text
    assert "def show(self, req, resp):" in products_text
    assert "def edit(self, req, resp):" in products_text
    assert "def update(self, req, resp):" in products_text
    assert "def delete(self, req, resp):" in products_text


def _test_model_singular(app_root):
    model_text = (app_root / "models" / "profile.py").read_text()
    assert "class Profile(Base):" in model_text

    init_text = (app_root / "models" / "__init__.py").read_text()
    assert init_text.strip() == "from .profile import *  # noqa"


def _test_migration_singular(app_root):
    migration = app_root / ".." / "db" / "migrations" / "2012_01_14_032134_create_profiles.py"
    assert migration.exists()

    content = migration.read_text()
    assert "class CreateProfiles(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
    assert 'self.schema.create("profiles") as table:' in content


def _test_templates_singular(app_root):
    templates = app_root / "templates" / "profile"
    assert templates.is_dir()
    assert not (templates / "index.html.jinja").exists()
    assert (templates / "new.html.jinja").exists()
    assert (templates / "show.html.jinja").exists()
    assert (templates / "edit.html.jinja").exists()


def _test_routes_singular(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""routes = [
    get("", to=Pages.index),

    resource("profile", to=Profile, singular=True),
]

""")
