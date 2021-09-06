import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender


MODEL_BLUEPRINT = BLUEPRINTS / "model"


def gen_model(app, name, *attrs):
    """Stubs out a new model.

    Pass the model name (singular), and an optional list of attribute pairs
    as arguments.

    You don't have to think up every attribute up front, but it helps to
    sketch out a few so you can start working with the model immediately.

    There are many ways to declare a model in SQLAlchemy. This tool does not cover
    all but try instead to be simple enough to be easy to use for the most
    common scenarios.

    ## Declaring fields

        ./manage.py g model NAME [field[:type[-options]][:attribute[-value]] ...]

    Attribute pairs are field:type arguments specifying the
    model's attributes. Timestamps are added by default, so you **don't have**
    to specify them by hand as 'created_at:datetime updated_at:datetime'.

    An `id` primary key will be also added by default. You can edit it later if you want
    another name or type a primary key.


    ### Field types:

    Just after the field name you can specify a type like text or boolean.
    It will generate the column with the associated SQL type. For instance:

        ./manage.py g model Post title:string body:text

    will generate a title column with a varchar type and a body column with a text
    type. If no type is specified the string type will be used by default.
    You can use the following types:

        - integer
        - string
        - text
        - boolean
        - datetime
        - date
        - time
        - float
        - numeric
        - interval
        - json
        - binary

    After the type, you can add one or more options. For example, for integer, string, and binary fields, an
    integer be set as the limit:

        ./manage.py g model User name:string-30

    for numeric fields, two integers separated by a dash will be used for precision and scale:

        ./manage.py g model Product price:numeric-10-2

    and so on.


    ### Field constraints:

    After the field type, you can add one or more pairs of `constraint` or `constraint-value`.
    The following constraints are supported:

    - unique
    - index
    - nullable
    - default
    - foreign

    If you don't use a value, it defaults to `True`.

    Use `foreign` for adding a foreign key:

        ./manage.py g model Post author_id:integer:foreign-users.id

    ### Example:

        `./manage.py g model Post title:string-30 body:text author_id:integer:foreign-users.id`

        class Post(Base, Timestamped):
            __tablename__ = "posts"
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(30))
            body = db.Column(db.Text)
            author_id = db.Column(db.Integer, db.ForeignKey("users.id"))


    ## Declaring relationships

        ./manage.py g model NAME [ field:Model[:backref[-lazy]][:lazy] ]

    ### Examples:

    - Simple backref:

            `./manage.py g model Post tags:Tag:post:joined`

            class Post(Base, Timestamped):
                __tablename__ = "posts"
                id = db.Column(db.Integer, primary_key=True)
                tags = db.relationship(
                    "Tag",
                    backref=db.backref("post"),
                    lazy="joined"
                )

    - Backref with lazy type:

            `./manage.py g model Post tags:Tag:posts-select:joined`

            class Post(Base, Timestamped):
                __tablename__ = "posts"
                id = db.Column(db.Integer, primary_key=True)
                tags = db.relationship(
                    "Tag",
                    backref=db.backref("post", lazy="select"),
                    lazy="joined"
                )

    - Implicit backref and lazy type:

            `./manage.py g model Post tags:Tag`

            class Post(Base, Timestamped):
                __tablename__ = "posts"
                id = db.Column(db.Integer, primary_key=True)
                tags = db.relationship(
                    "Tag",
                    backref=db.backref("posts"),
                    lazy="select"
                )

    """
    name = inflection.singularize(name)
    class_name = inflection.camelize(name)
    snake_name = inflection.underscore(name)
    table_name = inflection.tableize(class_name)
    rows = [_build_row(snake_name, attr) for attr in attrs]

    bp = BlueprintRender(
        MODEL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "class_name": class_name,
            "snake_name": snake_name,
            "table_name": table_name,
            "rows": rows,
        },
    )
    bp()


DEFAULT_FIELD_TYPE = "string"

COLUMN_TYPES = {
    "binary" : "LargeBinary",
    "boolean" : "Boolean",
    "date" : "Date",
    "datetime" : "DateTime",
    "decimal" : "Numeric",
    "float" : "Float",
    "integer" : "Integer",
    "interval" : "Interval",
    "json" : "JSON",
    "numeric" : "Numeric",
    "string" : "String",
    "text" : "Text",
    "time" : "Time",
}
FOREIGN_CONSTRAINT = "foreign"
CONSTRAINTS = ("unique", "index", "nullable", "default", FOREIGN_CONSTRAINT)


def _build_row(snake_name, attr):
    name, ctype, extra = (f"{attr}::").split(":", 2)
    ctype = ctype or DEFAULT_FIELD_TYPE
    extra = extra.rstrip(":")
    options = ""
    if "-" in ctype:
        ctype, options = ctype.split("-", 1)

    ColumnType = COLUMN_TYPES.get(ctype.lower())
    if ColumnType:
        col = _field(ColumnType, options, extra)
    else:
        ctype = inflection.camelize(ctype)
        col = _relationship(snake_name, ctype, extra)

    return f"{name} = {col}"


def _field(ColumnType, options, constraints):
    options = options.replace("-", ", ")
    options = f"({options})" if options else ""
    constraints = _build_constraints(constraints) if constraints else ""
    constraints = f", {constraints}" if constraints else ""
    return f"db.Column(db.{ColumnType}{options}{constraints})"


def _build_constraints(constraints):
    return ", ".join([
        _build_constraint(constraint) for constraint in constraints.split(":")
    ])


def _build_constraint(constraint):
    constraint, value = f"{constraint}-".split("-", 1)
    value = value.rstrip("-")

    assert constraint in CONSTRAINTS, f"Invalid constraint `{constraint}`"
    if constraint == FOREIGN_CONSTRAINT:
        assert value, "Missing column for foreign key. Use `foreign-table.column`"
        return f'db.ForeignKey("{value}")'
    else:
        value = False if value.lower() == "false" else True
        return f"{constraint}={value}"


def _relationship(snake_name, Model, constraints):
    backref, lazy = f"{constraints}:".split(":", 1)
    lazy = lazy.rstrip(":") or "select"
    backref = _build_backref(snake_name, backref)
    return f'db.relationship("{Model}", backref={backref}, lazy="{lazy}")'


def _build_backref(snake_name, backref):
    if not backref:
        snake_name = inflection.tableize(snake_name)
        return f'db.backref("{snake_name}")'
    backref, lazy = f"{backref}-".split("-", 1)
    lazy = lazy.rstrip("-")
    lazy = f', lazy="{lazy}"' if lazy else ""
    return f'db.backref("{backref}"{lazy})'
