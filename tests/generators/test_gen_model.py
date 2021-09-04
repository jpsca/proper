from proper.generators import gen_model


def test_base_model(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(app, "Product")

    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(Base):" in model_text

    init_text = (app_root / "models" / "__init__.py").read_text()
    assert init_text.strip() == "from .product import *  # noqa"
