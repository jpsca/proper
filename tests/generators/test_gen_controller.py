from proper.generators import gen_controller


def test_gen_controller(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_controller(app, "Products", "index", "show")

    products_text = (app_root / "controllers" / "products.py").read_text()
    assert "class Products(ApplicationController):" in products_text
    assert "def index(self):" in products_text
    assert "def show(self):" in products_text

    templates = app_root / "templates" / "products"
    assert templates.is_dir()
    assert (templates / "index.html.jinja").exists()
    assert (templates / "show.html.jinja").exists()


def test_routes_updated(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_controller(app, "Products", "index", "show")

    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""routes = [
    get("", to=Pages.index),

    get("products/index", to=Products.index),
    get("products/show", to=Products.show),
]

""")
