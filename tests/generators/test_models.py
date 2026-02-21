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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _split_attr
# ---------------------------------------------------------------------------


class TestSplitAttr:
    def test_name_only_defaults_to_str(self):
        assert _split_attr("title") == ("title", "str", [])

    def test_name_with_type(self):
        assert _split_attr("body:text") == ("body", "text", [])

    def test_single_option_flag(self):
        assert _split_attr("slug:str,unique") == ("slug", "str", ["unique=True"])

    def test_multiple_options(self):
        assert _split_attr("slug:str,unique,index") == (
            "slug", "str", ["unique=True", "index=True"]
        )

    def test_option_with_value(self):
        assert _split_attr("stock:int,default:0") == (
            "stock", "int", ["default=0"]
        )

    def test_type_aliases(self):
        assert _split_attr("a:string")[1] == "str"
        assert _split_attr("a:char")[1] == "str"
        assert _split_attr("a:boolean")[1] == "bool"
        assert _split_attr("a:integer")[1] == "int"
        assert _split_attr("a:numeric")[1] == "decimal"
        assert _split_attr("a:binary")[1] == "blob"

    def test_type_case_insensitive(self):
        assert _split_attr("a:STRING")[1] == "str"
        assert _split_attr("a:Boolean")[1] == "bool"

    def test_foreign_key_type_preserved(self):
        name, ftype, options = _split_attr("user:fk-User,backref:tweets")
        assert name == "user"
        assert ftype == "fk-User"
        assert options == ['backref="tweets"']

    def test_foreign_key_single_quoted_backref(self):
        _, _, options = _split_attr("user:fk-User,backref:'tweets'")
        assert options == ['backref="tweets"']


# ---------------------------------------------------------------------------
# _build_option
# ---------------------------------------------------------------------------


class TestBuildOption:
    def test_flag_defaults_to_true(self):
        assert _build_option("unique") == "unique=True"

    def test_value_preserved(self):
        assert _build_option("default:0") == "default=0"

    def test_false_normalised(self):
        assert _build_option("null:false") == "null=False"
        assert _build_option("null:FALSE") == "null=False"

    def test_backref_quoted(self):
        assert _build_option("backref:tweets") == 'backref="tweets"'

    def test_backref_single_to_double_quotes(self):
        assert _build_option("backref:'tweets'") == 'backref="tweets"'

    def test_string_default(self):
        assert _build_option('default:"fruit"') == 'default="fruit"'


# ---------------------------------------------------------------------------
# _field
# ---------------------------------------------------------------------------


class TestField:
    @pytest.mark.parametrize("ftype,expected", [
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
    ])
    def test_known_types(self, ftype, expected):
        assert _field(ftype, []) == expected

    def test_with_options(self):
        assert _field("str", ["unique=True", "index=True"]) == (
            "pw.CharField(unique=True, index=True)"
        )

    def test_case_insensitive(self):
        assert _field("STR", []) == "pw.CharField()"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid field type `foo`"):
            _field("foo", [])


# ---------------------------------------------------------------------------
# _foreign
# ---------------------------------------------------------------------------


class TestForeign:
    def test_basic(self):
        assert _foreign("fk-User", []) == "pw.ForeignKeyField(User)"

    def test_with_backref(self):
        assert _foreign("fk-User", ['backref="tweets"']) == (
            'pw.ForeignKeyField(User, backref="tweets")'
        )

    def test_multiple_options(self):
        assert _foreign("fk-User", ['backref="tweets"', "null=True"]) == (
            'pw.ForeignKeyField(User, backref="tweets", null=True)'
        )


# ---------------------------------------------------------------------------
# _build_row / _build_rows
# ---------------------------------------------------------------------------


class TestBuildRow:
    def test_simple(self):
        assert _build_row("name", "str", []) == "name = pw.CharField()"

    def test_with_options(self):
        assert _build_row("slug", "str", ["unique=True"]) == (
            "slug = pw.CharField(unique=True)"
        )

    def test_foreign_key(self):
        assert _build_row("user", "fk-User", ['backref="tweets"']) == (
            'user = pw.ForeignKeyField(User, backref="tweets")'
        )


class TestBuildRows:
    def test_empty(self):
        assert _build_rows([]) == []

    def test_multiple(self):
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


# ---------------------------------------------------------------------------
# gen_model  (integration — renders to tmp filesystem)
# ---------------------------------------------------------------------------


class TestGenModel:
    def test_generates_model_file(self, app_in_tmp):
        gen_model(app_in_tmp, "Product")
        text = _model_text(app_in_tmp, "product")
        assert "class Product(BaseModel):" in text
        assert "name = pw.CharField()" in text  # default row

    def test_appends_to_init(self, app_in_tmp):
        gen_model(app_in_tmp, "Product")
        init = _init_text(app_in_tmp)
        assert "from .product import Product" in init

    def test_custom_fields(self, app_in_tmp):
        gen_model(app_in_tmp, "Product", "name", "description:text", "stock:int")
        text = _model_text(app_in_tmp, "product")
        assert "name = pw.CharField()" in text
        assert "description = pw.TextField()" in text
        assert "stock = pw.IntegerField()" in text

    def test_fields_with_constraints(self, app_in_tmp):
        gen_model(
            app_in_tmp, "Product",
            "slug:str,unique,index",
            'type:str,default:"fruit"',
            "stock:int,default:0",
        )
        text = _model_text(app_in_tmp, "product")
        assert "slug = pw.CharField(unique=True, index=True)" in text
        assert 'type = pw.CharField(default="fruit")' in text
        assert "stock = pw.IntegerField(default=0)" in text

    def test_foreign_key(self, app_in_tmp):
        gen_model(app_in_tmp, "Tweet", "user:fk-User,backref:tweets")
        text = _model_text(app_in_tmp, "tweet")
        assert 'user = pw.ForeignKeyField(User, backref="tweets")' in text

    def test_imports_in_generated_file(self, app_in_tmp):
        gen_model(app_in_tmp, "Product")
        text = _model_text(app_in_tmp, "product")
        assert "import peewee as pw" in text
        assert "from .base import BaseModel" in text

    def test_no_migration_by_default(self, app_in_tmp):
        gen_model(app_in_tmp, "Product")
        # No call() invoked — just verify the file was generated
        text = _model_text(app_in_tmp, "product")
        assert "class Product(BaseModel):" in text

    def test_migration_still_generates_files(self, app_in_tmp):
        gen_model(app_in_tmp, "Product", migration=True)
        text = _model_text(app_in_tmp, "product")
        assert "class Product(BaseModel):" in text

    def test_returns_parsed_attrs(self, app_in_tmp):
        result = gen_model(app_in_tmp, "Product", "name", "stock:int")
        assert result == [
            ("name", "str", []),
            ("stock", "int", []),
        ]

    def test_name_inflection_from_snake(self, app_in_tmp):
        gen_model(app_in_tmp, "blog_post")
        text = _model_text(app_in_tmp, "blog_post")
        assert "class BlogPost(BaseModel):" in text

    def test_name_override(self, app_in_tmp):
        gen_model(
            app_in_tmp, "whatever",
            __name_snake="custom_model",
            __name_pascal="CustomModel",
        )
        text = _model_text(app_in_tmp, "custom_model")
        assert "class CustomModel(BaseModel):" in text

    def test_complex_model(self, app_in_tmp):
        gen_model(
            app_in_tmp, "Tweet",
            "body:text",
            "created_at:datetime",
            "user:fk-User,backref:tweets",
        )
        text = _model_text(app_in_tmp, "tweet")
        assert "class Tweet(BaseModel):" in text
        assert "body = pw.TextField()" in text
        assert "created_at = pw.DateTimeField()" in text
        assert 'user = pw.ForeignKeyField(User, backref="tweets")' in text
