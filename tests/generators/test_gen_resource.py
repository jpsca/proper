from unittest.mock import Mock
from proper.generators import resource as module


def test_gen_resource(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Products")

    _test_view(app_root)
    _test_model(app_root)
    _test_components(app_root)
    _test_routes(app_root)
    module.call.assert_not_called


def test_gen_resource_with_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Products", migration=True)
    module.call.assert_called_once_with('bin/proper db create "products"')


def _test_view(app_root):
    products_text = (app_root / "views" / "products" / "products.py").read_text()
    print(products_text)
    assert "class Products(AppView):" in products_text
    assert "def index(self):" in products_text
    assert "def new(self):" in products_text
    assert "def create(self):" in products_text
    assert "def show(self):" in products_text
    assert "def edit(self):" in products_text
    assert "def update(self):" in products_text
    assert "def delete(self):" in products_text


def _test_model(app_root):
    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(BaseModel):" in model_text


def _test_components(app_root):
    components = app_root / "components" / "Products"
    assert components.is_dir()
    assert (components / "Index.jinja").exists()
    assert (components / "New.jinja").exists()
    assert (components / "Show.jinja").exists()
    assert (components / "Edit.jinja").exists()


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

    _test_view_singular(app_root)
    _test_model_singular(app_root)
    _test_components_singular(app_root)
    _test_routes_singular(app_root)
    module.call.assert_not_called


def test_gen_resource_singular_with_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_resource(app, "Profile", singular=True, migration=True)
    module.call.assert_called_once_with('bin/proper db create "profile"')


def _test_view_singular(app_root):
    products_text = (app_root / "views" / "profile" / "profile.py").read_text()
    assert "class Profile(AppView):" in products_text
    assert "def index(self):" not in products_text
    assert "def new(self):" in products_text
    assert "def create(self):" in products_text
    assert "def show(self):" in products_text
    assert "def edit(self):" in products_text
    assert "def update(self):" in products_text
    assert "def delete(self):" in products_text


def _test_model_singular(app_root):
    model_text = (app_root / "models" / "profile.py").read_text()
    assert "class Profile(BaseModel):" in model_text


def _test_components_singular(app_root):
    components = app_root / "components" / "Profile"
    assert components.is_dir()
    assert not (components / "Index.jinja").exists()
    assert (components / "New.jinja").exists()
    assert (components / "Show.jinja").exists()
    assert (components / "Edit.jinja").exists()


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

    _test_view_only(app_root)
    _test_components_only(app_root)
    _test_routes_only(app_root)


def _test_view_only(app_root):
    text = (app_root / "views" / "persons" / "persons.py").read_text()
    assert "class Persons(AppView):" in text
    assert "def index(self):" not in text
    assert "def new(self):" not in text
    assert "def create(self):" in text
    assert "def show(self):" not in text
    assert "def edit(self):" not in text
    assert "def update(self):" in text
    assert "def delete(self):" not in text


def _test_components_only(app_root):
    components = app_root / "components" / "Persons"
    assert components.is_dir()
    assert not (components / "Index.jinja").exists()
    assert not (components / "New.jinja").exists()
    assert not (components / "Show.jinja").exists()
    assert not (components / "Edit.jinja").exists()


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

    _test_view_exclude(app_root)
    _test_components_exclude(app_root)
    _test_routes_exclude(app_root)


def _test_view_exclude(app_root):
    text = (app_root / "views" / "persons" / "persons.py").read_text()
    assert "class Persons(AppView):" in text
    assert "def index(self):" in text
    assert "def new(self):" in text
    assert "def create(self):" in text
    assert "def show(self):" in text
    assert "def edit(self):" not in text
    assert "def update(self):" not in text
    assert "def delete(self):" in text


def _test_components_exclude(app_root):
    components = app_root / "components" / "Persons"
    assert components.is_dir()
    assert (components / "Index.jinja").exists()
    assert (components / "New.jinja").exists()
    assert (components / "Show.jinja").exists()
    assert not (components / "Edit.jinja").exists()


def _test_routes_exclude(app_root):
    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""
    resource("persons", to=Persons, exclude="edit,update"),
]
""")
