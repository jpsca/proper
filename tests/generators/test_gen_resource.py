from unittest.mock import Mock
from proper.generators import resource as module


def test_gen_resource(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Products")

    _test_controller(app_root)
    _test_model(app_root)
    _test_components(app_root)
    _test_routes(app_root)
    module.call.assert_not_called


def test_gen_resource_with_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Products", migration=True)
    module.call.assert_called_once_with('proper db revision "Create products table"')


def _test_controller(app_root):
    products_text = (app_root / "controllers" / "products" / "products.py").read_text()
    print(products_text)
    assert "class Products(AppController):" in products_text
    assert "def index(self):" in products_text
    assert "def new(self):" in products_text
    assert "def create(self):" in products_text
    assert "def show(self):" in products_text
    assert "def edit(self):" in products_text
    assert "def update(self):" in products_text
    assert "def delete(self):" in products_text


def _test_model(app_root):
    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(Timestamped, db.Model):" in model_text


def _test_components(app_root):
    components = app_root / "components" / "products"
    assert components.is_dir()
    assert (components / "ProductsIndex.html.jinja").exists()
    assert (components / "ProductsNew.html.jinja").exists()
    assert (components / "ProductsShow.html.jinja").exists()
    assert (components / "ProductsEdit.html.jinja").exists()


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
    module.call = Mock()
    module.gen_resource(app, "Profile", singular=True)

    _test_controller_singular(app_root)
    _test_model_singular(app_root)
    _test_components_singular(app_root)
    _test_routes_singular(app_root)
    module.call.assert_not_called


def test_gen_resource_singular_with_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Profile", singular=True, migration=True)
    module.call.assert_called_once_with('proper db revision "Create profiles table"')


def _test_controller_singular(app_root):
    products_text = (app_root / "controllers" / "profile" / "profile.py").read_text()
    assert "class Profile(AppController):" in products_text
    assert "def index(self):" not in products_text
    assert "def new(self):" in products_text
    assert "def create(self):" in products_text
    assert "def show(self):" in products_text
    assert "def edit(self):" in products_text
    assert "def update(self):" in products_text
    assert "def delete(self):" in products_text


def _test_model_singular(app_root):
    model_text = (app_root / "models" / "profile.py").read_text()
    assert "class Profile(Timestamped, db.Model):" in model_text


def _test_components_singular(app_root):
    components = app_root / "components" / "profile"
    assert components.is_dir()
    assert not (components / "ProfileIndex.html.jinja").exists()
    assert (components / "ProfileNew.html.jinja").exists()
    assert (components / "ProfileShow.html.jinja").exists()
    assert (components / "ProfileEdit.html.jinja").exists()


def _test_routes_singular(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""routes = [
    get("", to=Pages.index),
    resource("profile", to=Profile, singular=True),
]
""")


def test_gen_resource_only(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Persons", only="create,update")

    _test_controller_only(app_root)
    _test_components_only(app_root)
    _test_routes_only(app_root)


def _test_controller_only(app_root):
    text = (app_root / "controllers" / "persons" / "persons.py").read_text()
    assert "class Persons(AppController):" in text
    assert "def index(self):" not in text
    assert "def new(self):" not in text
    assert "def create(self):" in text
    assert "def show(self):" not in text
    assert "def edit(self):" not in text
    assert "def update(self):" in text
    assert "def delete(self):" not in text


def _test_components_only(app_root):
    components = app_root / "components" / "persons"
    assert components.is_dir()
    assert not (components / "PersonsIndex.html.jinja").exists()
    assert not (components / "PersonsNew.html.jinja").exists()
    assert not (components / "PersonsShow.html.jinja").exists()
    assert not (components / "PersonsEdit.html.jinja").exists()


def _test_routes_only(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""
    resource("persons", to=Persons, only="create,update"),
]
""")


def test_gen_resource_exclude(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Persons", exclude="edit,update")

    _test_controller_exclude(app_root)
    _test_components_exclude(app_root)
    _test_routes_exclude(app_root)


def _test_controller_exclude(app_root):
    text = (app_root / "controllers" / "persons" / "persons.py").read_text()
    assert "class Persons(AppController):" in text
    assert "def index(self):" in text
    assert "def new(self):" in text
    assert "def create(self):" in text
    assert "def show(self):" in text
    assert "def edit(self):" not in text
    assert "def update(self):" not in text
    assert "def delete(self):" in text


def _test_components_exclude(app_root):
    components = app_root / "components" / "persons"
    assert components.is_dir()
    assert (components / "PersonsIndex.html.jinja").exists()
    assert (components / "PersonsNew.html.jinja").exists()
    assert (components / "PersonsShow.html.jinja").exists()
    assert not (components / "PersonsEdit.html.jinja").exists()


def _test_routes_exclude(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""
    resource("persons", to=Persons, exclude="edit,update"),
]
""")
