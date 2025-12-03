from typing import TYPE_CHECKING

import inflection

from proper.helpers import BLUEPRINTS
from proper.helpers.render import call, render_blueprint
from proper.router import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_RESTORE,
    ACTION_SHOW,
    ACTION_UPDATE,
)
from .model import gen_model


if TYPE_CHECKING:
    from proper.core.app import App


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"
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
    ACTION_RESTORE,
    ACTION_SHOW,
    ACTION_UPDATE,
)


def gen_resource(
    app: "App",
    name: str,
    *attrs: str,
    singular: bool = False,
    only: str = "",
    exclude: str = "",
    restore: bool = False,
    migration: bool = False,
    parent: str = "",
) -> None:
    """Stubs out a new resource including a controller, model, and views.

    Use `--migration` to also generate a migration for creating the table.

        proper g resource NAME
            [attrs...]
            [--only=action[,action]] [--exclude=action[,action]] [--singular]

    Arguments:
        name:
            The PascalCased resource name.

        attrs:
            Optional list of `field:type` columns for the model schema.
            Run `proper g model --help` for more information.

        singular [False]:
            Whether the resource represents a single entity for the user (like "profile").

        only:
            Optional comma-separated list of actions to include,
            instead of the full set.

        exclude:
            Optional comma-separated list of actions to exclude
            from the full set.

        restore [False]:
            Whether to include a `RESTORE` action in the default list of actions.

        migration [False]:
            Generate a migration for creating the table.

        parent:
            Optional PascalCased name of the "parent" resource.
            This will change how the routes and the views are generated.
            For example:

                proper g resource List

            will generate routes like:

                /list/
                /list/123
                ...

            but:

                proper g resource Item --parent List

            will generate routes "mounted" on a List resource like:

                /list/123/items
                /list/123/items/456
                ...

    By default, it generates the full set of REST actions ("index", "new", "create",
    "show", "edit", "update", and "delete"). You can opt for a subset of these
    or exclude specific ones using the `only` and `exclude` arguments.

    For resources that users always look up without an ID, use `singular=True`
    to create REST routes that do not include `:pk`.

    Examples:

        proper g resource Post
        proper g resource Post --only=index,show title:str
        proper g resource Post title:str body:text published:bool
        proper g resource Profile --singular

    """
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
    if restore:
        actions.add(ACTION_RESTORE)

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
        "restore": restore,
        "form_fields": form_fields,
        "form_class": f"{name_pascal}Form",
        "load_method": f"load_{name_snake}",
        "object": f"self.{name_snake}",
        "object_id": f"{name_snake}_id",
        "parent": None,
    }

    if parent:
        parent_name_snake = inflection.underscore(parent)
        context.update({
            "parent_name_snake": parent_name_snake,
            "parent": f"self.{parent_name_snake}",
            "parent_id": f"{parent_name_snake}_id",
        })

    render_blueprint(
        RESOURCE_BLUEPRINT,
        app.root_path.parent,
        context=context,
        ignore=ignored_views,
    )

    if migration:
        call(f'proper db create "{name_snake}"')
