import typing as t

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, call, sort_imports_in


if t.TYPE_CHECKING:
    from proper import App


MODEL_BLUEPRINT = BLUEPRINTS / "model"

SORT_IMPORTS_IN = [
    "models/__init__.py",
]


def gen_model(
    app: "App",
    name: str,
    *attrs: str,
    migration: bool = False,
    singular_pascal: str = "",
    singular_snake: str = "",
    plural_snake: str = "",
) -> list[tuple[str, str, list[str]]]:
    """Stubs a new model based on [Peewee ORM](https://docs.peewee-orm.com)

    Arguments:

    - name:
        The PascalCased model name, always singular.

    - migration [False]:
        Generate a migration for creating the table.

    - attrs:
        Optional list of columns for the model schema.

    You don't have to think up every attribute upfront, but it helps to
    sketch out a few so you can start working with the model immediately.

    There are many ways to declare a model. This tool does not cover
    all but tries instead to be simple enough to be easy to use for the most
    common scenarios.

    ## Declaring fields

        proper g model NAME [field_name[:type][,option[:value]]...]

    Attribute pairs are field_name:type arguments specifying the model's attributes.
    An `id` primary key will be implicit unless you mark a field with `primary_key=True`.

    ## Field types

    Right after the field name, you can specify a type like text or boolean.
    It will generate the column with the associated SQL type. For instance:

        proper g model Post title:str body:text

    will generate a title column with a varchar type and a body column with a text
    type. If no type is specified, the string type will be used by default.
    You can use the following types:

    - bigint
    - blob
    - bool
    - date
    - datetime
    - decimal
    - float
    - int
    - str
    - text
    - time
    - uuid
    - fk

    ## Options

    After the field type, you can add one or more pairs of `option` or `option:value`,
    like `unique`, `null`, `default`, `index`, etc.
    See http://docs.peewee-orm.com/en/latest/peewee/models.html#field-initialization-arguments.

    If you don't use a value, it defaults to `True`.

    Use `fk-MODEL` for adding a foreign key.

    ## Examples:

        `proper g model Tweet body:text created_at:datetime user:fk-User,backref:'tweets'`

        import peewee as pw

        class Tweet(BaseModel):
            body = pw.TextField()
            created_at = pw.DateTimeField()
            user = pw.ForeignKeyField(User, backref='tweets').

    """
    singular_name = inflection.singularize(name)
    singular_pascal = singular_pascal or inflection.camelize(singular_name)
    singular_snake = singular_snake or inflection.underscore(singular_name)
    plural_snake = plural_snake or inflection.tableize(singular_pascal)
    attrs_tuples = [_split_attr(attr) for attr in attrs]
    rows = _build_rows(attrs_tuples)

    bp = BlueprintRender(
        MODEL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "singular_pascal": singular_pascal,
            "singular_snake": singular_snake,
            "plural_snake": plural_snake,
            "rows": rows or ["name = pw.CharField()"],
        },
    )
    bp()

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    if migration:
        call(f'proper db create "{plural_snake}"')

    return attrs_tuples


def _split_attr(attr: str) -> tuple[str, str, list[str]]:
    name_ftype, *options = attr.split(",")
    if ":" in name_ftype:
        name, ftype = name_ftype.split(":", 1)
        ftype = TYPE_TRANSLATIONS.get(ftype.lower(), ftype)
    else:
        name = name_ftype
        ftype = DEFAULT_FIELD_TYPE

    options = [_build_option(option) for option in options]
    return name, ftype, options


def _build_option(option: str) -> str:
    key, value = f"{option}:".split(":", 1)
    value = value.rstrip(":") or "True"
    if value.lower() == "false":
        value = "False"
    return f"{key}={value}"


DEFAULT_FIELD_TYPE = "str"
TYPE_TRANSLATIONS = {
    "binary": "blob",
    "boolean": "bool",
    "numeric": "decimal",
    "integer": "int",
    "char": "str",
    "string": "str",
}

FIELD_TYPES = {
    "bigint": "BigIntegerField",
    "blob": "BlobField",
    "bool": "BooleanField",
    "date": "DateField",
    "datetime": "DateTimeField",
    "decimal": "DecimalField",
    "float": "FloatField",
    "int": "IntegerField",
    "str": "CharField",
    "text": "TextField",
    "time": "TimeField",
    "uuid": "UUIDField",
}


def _build_rows(attrs: list[tuple[str, str, list[str]]]) -> list[str]:
    return [_build_row(name, ftype, options) for name, ftype, options in attrs]


def _build_row(name: str, ftype: str, options: list[str]) -> str:
    if ftype.lower().startswith("fk-"):
        field = _foreign(ftype, options)
    else:
        field = _field(ftype, options)

    return f"{name} = {field}"


def _foreign(ftype: str, options: list[str]) -> str:
    model = ftype.split("-", 1)[-1]
    field_options = ", ".join(options)
    field_options = f", {field_options}" if field_options else ""
    return f"pw.ForeignKeyField({model}{field_options})"


def _field(ftype: str, options: list[str]) -> str:
    FieldType = FIELD_TYPES.get(ftype.lower())
    if not FieldType:
        raise ValueError(f"Invalid field type `{ftype}`")

    field_options = ", ".join(options)
    return f"pw.{FieldType}({field_options})"
