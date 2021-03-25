from datetime import datetime

import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender


MIGRATION_BLUEPRINT = BLUEPRINTS / "migration"
SCHEMA_GEN_DOC = """
# Description:

You don't have to think up every column up front, but it helps to
sketch out a few so you can start working with the model immediately.

There are many ways to declare a schema in Liquid ORM. This tool does not cover
all but try instead to be simple enough to be easy to use for the most
common scenarios.

Timestamps and an `id` primary key will be added by default. You can edit it later
if you don't want those defaults.


## Column types:

Just after the column name you can specify a type like text or boolean.
It will generate the column with the associated SQL type. For instance:

    bin/manage g {cmd} title:string body:text

will generate a title column with a varchar type and a body column with a text
type. If no type is specified the string type will be used by default.
You can use the following types:

- integer / small_integer / medium_integer / big_integer
- binary
- boolean
- char
- date
- datetime
- decimal
- float
- json
- text / medium_text / long_text
- string
- time

After the type, some columns accept one or more options. The string and char columns,
accept an integer as length, and the decimal column, two integers for precision and scale. Example:

    bin/manage g {cmd} name:string-30 price:decimal-5-2


## Constraints:

After the column type, you can add one or more`constraints. The following are supported:

- nullable
- unsigned
- unique
- index
- default-value
- foreign-table.col

Use "true" or "false" as the value of the `default` constraint, and it will be
converted to the booleans `True` or `False`

Example:

    bin/manage g {cmd} title:string-30:nullable is_draft:boolean:default-true


Use `foreign` for adding a foreign key:

    bin/manage g {cmd} author_id:integer:foreign-users.id

"""
DEFAULT_FIELD_TYPE = "string"
INTEGER_FIELD_TYPE = "integer"
DEFAULT_CONSTRAINT = "default"
FOREIGN_CONSTRAINT = "foreign"


def gen_migration(app, name, *attrs, table=None, create=False):
    name = name.replace(" ", "_")
    class_name = inflection.camelize(name)
    table = inflection.pluralize(table) if table else None
    snake_name = inflection.underscore(name)

    lines = []
    for attr in attrs:
        lines = _add_field(lines, attr)

    bp = BlueprintRender(
        MIGRATION_BLUEPRINT,
        app.root_path.parent,
        context={
            "dt": get_datestamp(),
            "snake_name": snake_name,
            "class_name": class_name,
            "table": table,
            "create": create,
            "lines": lines,
        },
    )
    bp()


gen_migration.__doc__ = """Stubs out a new migration file.

    bin/manage g migration NAME [--table table_name] [--update] [column[:type[-options]][:attribute[-value]] ...]

Arguments:

- name: The name of the migration.
- table: The name (plural) of thetable to create the migration for.
- create : Whether the migration will create the table instead of just updating it.
- attrs: Optional list of columns to add to the schema.

""" + SCHEMA_GEN_DOC.format(
    cmd='migration "setup" product'
)


def _add_field(lines, attr):
    name, ctype, extra = (f"{attr}::").split(":", 2)
    ctype = ctype or DEFAULT_FIELD_TYPE
    extra = extra.rstrip(":")
    options = ""
    if "-" in ctype:
        ctype, options = ctype.split("-", 1)

    ctype = ctype.lower()
    options = options.replace("-", ", ")
    options = f", {options})" if options else ""

    flines = [f'table.{ctype}("{name}"{options})']
    if extra:
        flines = _add_constraints(flines, name, ctype, extra)

    lines.extend(flines)
    return lines


def _add_constraints(flines, name, ctype, extra):
    fline = flines[0]

    for constraint in extra.split(":"):
        constraint, value = f"{constraint}-".split("-", 1)
        value = value.rstrip("-")

        if constraint == FOREIGN_CONSTRAINT:
            if ctype == INTEGER_FIELD_TYPE and ":unsigned" not in extra:
                fline = f"{fline}.unsigned()"

            assert value, "Missing column for foreign key. Use `foreign-table.column`"
            ftable, fcol = value.split(".")
            flines.append(f'table.foreign("{name}").references("{fcol}").on("{ftable}")')

        elif constraint == DEFAULT_CONSTRAINT:
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            fline = f'{fline}.default("{value}")'

        else:
            fline = f"{fline}.{constraint}()"

    flines[0] = fline
    return flines


def get_datestamp():
    return (
        str(datetime.utcnow())
        .split(".")[0]
        .replace("-", "_")
        .replace("T", "_")
        .replace(" ", "_")
        .replace(":", "")
    )
