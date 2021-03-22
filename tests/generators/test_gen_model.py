from freezegun import freeze_time

from proper.generators import gen_model


def test_base_model(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    gen_model(app, "Product")

    model_text = (app_root / "models" / "product.py").read_text()
    assert "class Product(Base):" in model_text

    init_text = (app_root / "models" / "__init__.py").read_text()
    assert init_text.strip() == "from .product import *  # noqa"


def test_migration_made(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    with freeze_time("2012-01-14 03:21:34"):
        gen_model(app, "Product")

    migration = app_root / ".." / "db" / "migrations" / "2012_01_14_032134_create_products.py"
    assert migration.exists()

    content = migration.read_text()
    assert "class CreateProducts(Migration):" in content
    assert "def up(self):" in content
    assert "def down(self):" in content
