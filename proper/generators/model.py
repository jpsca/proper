

def gen_model(app, name, *fields):
    """Stubs out a new model.

    Pass the PascalCased model name, and an optional list of attribute pairs
    as arguments.

    You don't have to think up every attribute up front, but it helps to
    sketch out a few so you can start working with the model immediately.

    There are many ways to declare a model in SQLAlchemy. This tool does not cover
    all but try instead to be simple enough to be easy to use for the most
    common scenarios.

    ## Declaring fields

        bin/manage g model NAME [field[:type[-options]][:attribute[-value]] ...]

    Attribute pairs are field:type arguments specifying the
    model's attributes. Timestamps are added by default, so you **don't have**
    to specify them by hand as 'created_at:datetime updated_at:datetime'.

    An `id` primary key will be also added by default. YTou can edit it later if you want
    another name or type a primary key.


    ### Field types:

    Just after the field name you can specify a type like text or boolean.
    It will generate the column with the associated SQL type. For instance:

        bin/manage g model post title:string body:text

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
        - binary
        - json

    After the type, you can add one or more options. For example, for integer, string, and binary fields, an
    integer be set as the limit:

        bin/manage g model user name:string-30

    for decimal, two integers separated by a dash will be used for precision and scale:

        bin/manage g model product price:decimal-10-2

    and so on.


    ### Field attributes:

    After the field type, you can add one or more pairs of `attribute` or attribute-value`.
    The following attributes are supported:

    - unique
    - index
    - nullable
    - default
    - foreign

    If you don't use a value, it defaults to `True`.

    Use `foreign` for adding a foreign key:

        bin/manage g model Post author_id:integer:foreign-users.id


    ## Declaring relationships

        bin/manage g model NAME [ field:Model[:backref[-lazy]][:lazy] ]

    Examples:

    - Simple backref:

            bin/manage g model Post -r tags:Tag:post:joined

        generates

            tags = db.relationship("Tag", backref=db.backref("post"), lazy="joined")

    - Backref with lazy type:

            bin/manage g model Post -r tags:Tag:post-select:joined

        generates

            tags = db.relationship("Tag", backref=db.backref("post", lazy="select"), lazy="joined")

    - Implicit backref and lazy type:

            bin/manage g model Post -r tags:Tag

        generates

            tags = db.relationship("Tag", backref=db.backref("post"), lazy="select")


    """
    pass
