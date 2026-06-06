import pytest

from proper.generators.model import (
    _build_option,
    _build_row,
    _build_rows,
    _field,
    _foreign,
    _split_attr,
    gen_model,
)


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the models/ directory pre-created,
    then point the app fixture at it."""
    app_root = tmp_path / APP_NAME
    models_dir = app_root / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


def _model_text(app, name_snake: str) -> str:
    return (app.root_path / "models" / f"{name_snake}.py").read_text()


def _init_text(app) -> str:
    return (app.root_path / "models" / "__init__.py").read_text()


def test_split_attr():
    assert _split_attr("title") == ("title", "str", [])
    assert _split_attr("body:text") == ("body", "text", [])
    assert _split_attr("slug:str,unique") == ("slug", "str", ["unique=True"])
    assert _split_attr("slug:str,unique,index") == (
        "slug",
        "str",
        ["unique=True", "index=True"],
    )
    assert _split_attr("stock:int,default:0") == ("stock", "int", ["default=0"])


def test_type_aliases():
    assert _split_attr("a:string")[1] == "str"
    assert _split_attr("a:char")[1] == "str"
    assert _split_attr("a:boolean")[1] == "bool"
    assert _split_attr("a:integer")[1] == "int"
    assert _split_attr("a:numeric")[1] == "decimal"
    assert _split_attr("a:binary")[1] == "blob"


def test_type_case_insensitive():
    assert _split_attr("a:STRING")[1] == "str"
    assert _split_attr("a:Boolean")[1] == "bool"


def test_foreign_key_type_preserved():
    name, ftype, options = _split_attr("user:fk-User,backref:tweets")
    assert name == "user"
    assert ftype == "fk-User"
    assert options == ['backref="tweets"']


def test_foreign_key_single_quoted_backref():
    _, _, options = _split_attr("user:fk-User,backref:'tweets'")
    assert options == ['backref="tweets"']


def test_build_flag_defaults_to_true():
    assert _build_option("unique") == "unique=True"


def test_build_value_preserved():
    assert _build_option("default:0") == "default=0"


def test_build_false_normalised():
    assert _build_option("null:false") == "null=False"
    assert _build_option("null:FALSE") == "null=False"


def test_build_quoted():
    assert _build_option("backref:tweets") == 'backref="tweets"'
    assert _build_option("on_delete:CASCADE") == 'on_delete="CASCADE"'


def test_build_backref_single_to_double_quotes():
    assert _build_option("backref:'tweets'") == 'backref="tweets"'


def test_build_string_default():
    assert _build_option('default:"fruit"') == 'default="fruit"'


def test_build_do_not_quote_bools_or_numbers():
    assert _build_option("null:True") == "null=True"
    assert _build_option("null:False") == "null=False"
    assert _build_option("default:0") == "default=0"
    assert _build_option("default:1.5") == "default=1.5"


@pytest.mark.parametrize(
    "ftype,expected",
    [
        ("bigint", "pw.BigIntegerField()"),
        ("blob", "pw.BlobField()"),
        ("bool", "pw.BooleanField()"),
        ("date", "pw.DateField()"),
        ("datetime", "pw.DateTimeField()"),
        ("decimal", "pw.DecimalField()"),
        ("float", "pw.FloatField()"),
        ("int", "pw.IntegerField()"),
        ("str", "pw.CharField()"),
        ("text", "pw.TextField()"),
        ("time", "pw.TimeField()"),
        ("uuid", "pw.UUIDField()"),
    ],
)
def test_known_types(ftype, expected):
    assert _field(ftype, []) == expected


def test_with_options():
    assert _field("str", ["unique=True", "index=True"]) == (
        "pw.CharField(unique=True, index=True)"
    )


def test_case_insensitive():
    assert _field("STR", []) == "pw.CharField()"


def test_invalid_type_raises():
    with pytest.raises(ValueError, match="Invalid field type `foo`"):
        _field("foo", [])


def test_foreign_basic():
    assert _foreign("fk-User", []) == "pw.ForeignKeyField(User)"


def test_foreign_with_backref():
    assert _foreign("fk-User", ['backref="tweets"']) == (
        'pw.ForeignKeyField(User, backref="tweets")'
    )


def test_foreign_multiple_options():
    assert _foreign("fk-User", ['backref="tweets"', "null=True"]) == (
        'pw.ForeignKeyField(User, backref="tweets", null=True)'
    )


def test_build_simple():
    assert _build_row("name", "str", []) == "name = pw.CharField()"


def test_build_with_options():
    assert _build_row("slug", "str", ["unique=True"]) == (
        "slug = pw.CharField(unique=True)"
    )


def test_build_foreign_key():
    assert _build_row("user", "fk-User", ['backref="tweets"']) == (
        'user = pw.ForeignKeyField(User, backref="tweets")'
    )


def test_build_empty():
    assert _build_rows([]) == []


def test_build_multiple():
    attrs = [
        ("name", "str", []),
        ("body", "text", []),
        ("count", "int", ["default=0"]),
    ]
    assert _build_rows(attrs) == [
        "name = pw.CharField()",
        "body = pw.TextField()",
        "count = pw.IntegerField(default=0)",
    ]


def test_generates_model_file(app_in_tmp):
    gen_model(app_in_tmp, "Product")
    text = _model_text(app_in_tmp, "product")
    assert "class Product(BaseModel):" in text
    assert "name = pw.CharField()" in text  # default row


def test_appends_to_init(app_in_tmp):
    gen_model(app_in_tmp, "Product")
    init = _init_text(app_in_tmp)
    assert "from .product import Product" in init


def test_custom_fields(app_in_tmp):
    gen_model(app_in_tmp, "Product", "name", "description:text", "stock:int")
    text = _model_text(app_in_tmp, "product")
    assert "name = pw.CharField()" in text
    assert "description = pw.TextField()" in text
    assert "stock = pw.IntegerField()" in text


def test_fields_with_constraints(app_in_tmp):
    gen_model(
        app_in_tmp,
        "Product",
        "slug:str,unique,index",
        'type:str,default:"fruit"',
        "stock:int,default:0",
    )
    text = _model_text(app_in_tmp, "product")
    assert "slug = pw.CharField(unique=True, index=True)" in text
    assert 'type = pw.CharField(default="fruit")' in text
    assert "stock = pw.IntegerField(default=0)" in text


def test_foreign_key(app_in_tmp):
    gen_model(app_in_tmp, "Tweet", "user:fk-User,backref:tweets")
    text = _model_text(app_in_tmp, "tweet")
    assert 'user = pw.ForeignKeyField(User, backref="tweets")' in text


def test_imports_in_generated_file(app_in_tmp):
    gen_model(app_in_tmp, "Product")
    text = _model_text(app_in_tmp, "product")
    assert "import peewee as pw" in text
    assert "from .base import BaseModel" in text


def test_no_migration_by_default(app_in_tmp):
    gen_model(app_in_tmp, "Product")
    # No call() invoked - just verify the file was generated
    text = _model_text(app_in_tmp, "product")
    assert "class Product(BaseModel):" in text


def test_migration_still_generates_files(app_in_tmp):
    gen_model(app_in_tmp, "Product", migration=True)
    text = _model_text(app_in_tmp, "product")
    assert "class Product(BaseModel):" in text


def test_name_inflection_from_snake(app_in_tmp):
    gen_model(app_in_tmp, "blog_post")
    text = _model_text(app_in_tmp, "blog_post")
    assert "class BlogPost(BaseModel):" in text


def test_name_override(app_in_tmp):
    gen_model(
        app_in_tmp,
        "whatever",
        _name_snake="custom_model",
        _name_pascal="CustomModel",
    )
    text = _model_text(app_in_tmp, "custom_model")
    assert "class CustomModel(BaseModel):" in text


def test_complex_model(app_in_tmp):
    gen_model(
        app_in_tmp,
        "Tweet",
        "body:text",
        "created_at:datetime",
        "user:fk-User,backref:tweets",
    )
    text = _model_text(app_in_tmp, "tweet")
    assert "class Tweet(BaseModel):" in text
    assert "body = pw.TextField()" in text
    assert "created_at = pw.DateTimeField()" in text
    assert 'user = pw.ForeignKeyField(User, backref="tweets")' in text
