from proper.generators import gen_controller


def test_gen_controller(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_controller(app, "Products", "index", "show")

    products_text = (app_root / "controllers" / "products.py").read_text()
    assert """"
    @router.resource("products")
    class ProductsController(AppController):
    """ in products_text
    assert "def index(self):" in products_text
    assert "def show(self):" in products_text

    components = app_root / "components" / "Products"
    assert components.is_dir()
    assert (components / "Index.jinja").exists()
    assert (components / "Show.jinja").exists()

