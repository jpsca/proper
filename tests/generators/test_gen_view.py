from proper.generators import gen_view


def test_gen_view(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_view(app, "Products", "index", "show")

    products_text = (app_root / "views" / "products.py").read_text()
    assert "class Products(AppView):" in products_text
    assert "def index(self):" in products_text
    assert "def show(self):" in products_text

    components = app_root / "components" / "Products"
    assert components.is_dir()
    assert (components / "Index.jinja").exists()
    assert (components / "Show.jinja").exists()


def test_routes_updated(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_view(app, "Products", "index", "show")

    routes_text = (app_root / "routes.py").read_text()
    print(routes_text)
    assert routes_text.endswith("""routes = [
    get("", to=Pages.index),

    get("products/index", to=Products.index),
    get("products/show", to=Products.show),
]
""")
