from typing import TYPE_CHECKING

import inflection

from ..helpers import BLUEPRINTS
from ..helpers.render import call, render_blueprint, sort_imports_in
from ..router import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_SHOW,
    ACTION_UPDATE,
)
from .model import gen_model


if TYPE_CHECKING:
    from ..app import App


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"

SORT_IMPORTS_IN = [
    "controllers/__init__.py",
]

FORM_FIELDS = {
    "bigint": "IntegerField",
    "bool": "BooleanField",
    "date": "DateField",
    "datetime": "DateTimeField",
    "decimal": "FloatField",
    "float": "FloatField",
    "int": "IntegerField",
    "str": "TextField",
    "text": "TextField",
    "time": "TimeField",
    "uuid": "TextField",
}

ACTIONS = (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_SHOW,
    ACTION_UPDATE,
)


def gen_resource(
    app: "App",
    name: str,
    *attrs: str,
    only: str = "",
    exclude: str = "",
    singular: bool = False,
    migration: bool = False,
    pk: str = "",
) -> None:
    """Stubs out a new resource including a controller, model, and views.

    Use `--migration` to also generate a migration for creating the table.

        proper g resource NAME
            [attrs...]
            [--only=action[,action]] [--exclude=action[,action]]
            [--pk=object_id] [--singular] [--migration]

    Arguments:
        name:
            The PascalCased resource name.

        attrs:
            Optional list of `field:type` columns for the model schema.
            Run `proper g model --help` for more information.

        only:
            Optional comma-separated list of actions to include,
            instead of the full set.

        exclude:
            Optional comma-separated list of actions to exclude
            from the full set.

        singular [False]:
            Whether the resource represents a single entity for the user (like "profile").

        migration [False]:
            Generate a migration for creating the table.

        pk:
            Optional name for the `:object_id` parameter
            (defaults to empty, so `[name_snakecased]_id` will be used
            in the generated URLs). Ignored if `singular` is `True`.

    By default, it generates the full set of REST actions ("index", "new", "create",
    "show", "edit", "update", and "delete"). You can opt for a subset of these
    or exclude specific ones using the `only` and `exclude` arguments.

    For resources that users always look up without an ID, use `singular=True`
    to create REST routes that do not include `:object_id`.

    Examples:

        proper g resource Post
        proper g resource Post --only=index,show title:str
        proper g resource Post title:str body:text published:bool
        proper g resource Profile --singular

    """
    pk = pk.strip().strip(":")

    name_pascal = inflection.camelize(name)
    name_snake = inflection.underscore(name)
    plural_snake = inflection.pluralize(name_snake)

    only_list = [ac for ac in list(dict.fromkeys(only.split(","))) if ac in ACTIONS]
    exclude_list = [ac for ac in list(dict.fromkeys(exclude.split(","))) if ac in ACTIONS]

    actions: set[str] = set(ACTIONS)
    if only_list:
        actions = actions.intersection(set(only_list))
    elif exclude_list:
        actions = actions.difference(set(exclude_list))
    if singular:
        actions.remove("index")

    ignored_actions = set(ACTIONS).difference(actions)
    ignored_views = []
    for action in ignored_actions:
        ignored_views.append(
            f"*{action}.tt.jinja",
        )

    attrs_tuples = gen_model(
        app,
        name,
        *attrs,
        migration=migration,
        __name_pascal=name_pascal,
        __name_snake=name_snake,
    )
    form_fields = [
        {
            "type": FORM_FIELDS.get(ftype) or "TextField",
            "name": name,
            "default": None,
        }
        for name, ftype, _options in attrs_tuples
        if ftype in FORM_FIELDS
    ]

    context = {
        "app_name": app.name,
        "name_pascal": name_pascal,
        "name_snake": name_snake,
        "plural_snake": plural_snake,
        "only": only_list,
        "exclude": exclude_list,
        "actions": actions,
        "singular": singular,
        "form_fields": form_fields,
        "form_class": f"{name_pascal}Form",
        "load_method": f"set_{name_snake}",
        "object": f"self.{name_snake}",
        "object_id": pk or f"{name_snake}_id",
        "pk": pk,
    }

    render_blueprint(
        RESOURCE_BLUEPRINT,
        app.root_path.parent,
        context=context,
        ignore=ignored_views,
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    if migration:
        call(f'proper db create "{name_snake}"')
