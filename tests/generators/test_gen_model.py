from unittest.mock import Mock
from proper.generators import model as module


def test_base_model(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_model(app, "Product")

    model_text = (app_root / "models" / "product.py").read_text()
    print(model_text)
    assert "class Product(BaseModel):" in model_text
    module.call.assert_not_called


def test_gen_model_with_migration(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.call = Mock()
    module.gen_model(app, "Product", migration=True)
    module.call.assert_called_once_with('proper db create "products"')


def test_fields(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.gen_model(
        app,
        "Product",
        "name",
        "description:text",
        "stock:int",
    )

    model_text = (app_root / "models" / "product.py").read_text()
    print(model_text)
    assert "name = CharField()" in model_text
    assert "description = TextField()" in model_text
    assert "stock = IntegerField()" in model_text


def test_constraints(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.gen_model(
        app,
        "Product",
        "slug:str,unique,index",
        'type:str,default:"fruit"',
        "stock:int,default:0",
    )

    model_text = (app_root / "models" / "product.py").read_text()
    print(model_text)
    assert "slug = CharField(unique=True, index=True)" in model_text
    assert 'type = CharField(default="fruit")' in model_text
    assert "stock = IntegerField(default=0)" in model_text


def test_foreign_key(app, scaffold):
    app_root = scaffold
    app.root_path = app_root
    module.gen_model(app, "Tweet", 'user:fk-User,backref:"tweets"')

    model_text = (app_root / "models" / "tweet.py").read_text()
    print(model_text)
    assert 'user = ForeignKeyField(User, backref="tweets")' in model_text
