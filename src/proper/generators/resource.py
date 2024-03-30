from typing import TYPE_CHECKING

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, call
from ..router.resource import ACTION_RESTORE, ACTIONS
from .model import gen_model


if TYPE_CHECKING:
    from proper import App


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"
ROUTES_TT = "routes.tt.py"
FORM_FIELDS = {
    "bigint": "int",
    "blob": "bytes",
    "bool": "bool",
    "date": "date",
    "datetime": "datetime",
    "decimal": "float",
    "float": "float",
    "int": "int",
    "str": "str",
    "text": "str",
    "time": "time",
    "uuid": "str",
}


def gen_resource(
    app: "App",
    name: str,
    *attrs: str,
    singular: bool = False,
    restore: bool = False,
    parent: str = "",
    only: str = "",
    exclude: str = "",
    migration: bool = False,
) -> None:
    """Stubs out a new resource including a view, model, migration, components
    and a route in the `routes.py` file.

    Use `--migration` to also generate a migration for creating the table.

        proper g resource NAME
            [--only=action[,action]] [--exclude=action[,action]] [--singular]

    Arguments:

    - name:
        The PascalCased resource name, plural unless `--singular` is used.

    - singular [False]:
        Whether the resource represents a single entity for the user (like "profile").

    - restore [False]:
        Whether to include a `RESTORE` action.

    - parent:
        Optional PascalCased name of the "parent" resource.
        This will change how the routes and the views are generated.
        For example:

            proper g resource List

        will generate routes like:

            /lists/
            /lists/123
            ...

        but:

            proper g resource Item --parent List

        will generate routes "mounted" on a List resource like:

            /list/123/items
            /list/123/items/456
            ...

    - only:
        Optional comma-separated list of actions to include,
        instead of the full set.

    - exclude:
        Optional comma-separated list of actions to exclude
        from the full set.

    - migration [False]:
        Generate a migration for creating the table.

    - attrs:
        Optional list of columns for the resource schema.

    Attribute pairs are `field:type` arguments, specifying the model's attributes,
    following the syntax of the model generator.
    For instructions, run `proper g model --help`.

    By default, it generates the full set of REST actions ("index", "new", "create",
    "show", "edit", "update", and "delete"). You can opt for a subset of these
    or exclude specific ones using the `only` and `exclude` arguments.

    For resources that users always look up without an ID, use `singular=True`
    to create REST routes that do not include `:pk`.

    Examples:

        proper g resource Posts
        proper g resource Posts --only=index,show title:str
        proper g resource Posts title:str body:text published:bool
        proper g resource Profile --singular

    """
    plural_name = inflection.pluralize(name)
    plural_pascal = inflection.camelize(plural_name)
    plural_snake = inflection.underscore(plural_name)

    singular_name = inflection.singularize(name)
    singular_pascal = inflection.camelize(singular_name)
    singular_snake = inflection.underscore(singular_name)

    view_snake = singular_snake if singular else plural_snake
    view_pascal = singular_pascal if singular else plural_pascal

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
    ignored_components = []
    for action in ignored_actions:
        action_pascal = inflection.camelize(action)
        ignored_components.append(
            f"*{action_pascal}.tt.jinja",
        )

    attrs_tuples = gen_model(
        app,
        name,
        *attrs,
        singular_pascal=singular_pascal,
        singular_snake=singular_snake,
        plural_snake=plural_snake,
        migration=migration,
    )
    form_fields = [
        {
            "type": FORM_FIELDS[ftype],
            "name": name,
            "default": None,
        }
        for name, ftype, _options in attrs_tuples
        if ftype in FORM_FIELDS
    ]

    context = {
        "app_name": app.root_path.name,
        "plural_pascal": plural_pascal,
        "plural_snake": plural_snake,
        "singular_pascal": singular_pascal,
        "singular_snake": singular_snake,
        "view_snake": view_snake,
        "view_pascal": view_pascal,
        "mount_point": view_snake,
        "only": only_list,
        "exclude": exclude_list,
        "actions": actions,
        "singular": singular,
        "restore": restore,
        "form_fields": form_fields,
        "form_class": f"{singular_pascal}Model",
        "load_method": f"load_{singular_snake}",
        "object": f"self.{singular_snake}",
        "object_id": f"{singular_snake}_id",
        "parent": None,
    }

    if parent:
        parent_plural_name = inflection.pluralize(parent)
        parent_plural_snake = inflection.underscore(parent_plural_name)

        parent_singular_name = inflection.singularize(parent)
        parent_singular_pascal = inflection.camelize(parent_singular_name)
        parent_singular_snake = inflection.underscore(parent_singular_name)

        context.update({
            "parent_plural_name": parent_plural_name,
            "parent_plural_snake": parent_plural_snake,
            "parent_singular_pascal": parent_singular_pascal,
            "parent_singular_snake": parent_singular_snake,
            "mount_point": f"{parent_plural_snake}/:{parent_singular_snake}_id/{view_snake}",
            "load_parent_method": f"load_{parent_singular_snake}",
            "parent": f"self.{parent_singular_snake}",
            "parent_id": f"{parent_singular_snake}_id",
        })

    bp = BlueprintRender(
        RESOURCE_BLUEPRINT,
        app.root_path.parent,
        context=context,
        ignore=[ROUTES_TT] + ignored_components,
    )
    bp()

    routes_tt = RESOURCE_BLUEPRINT / ROUTES_TT
    new_routes = bp.render.string(routes_tt.read_text())
    append_routes(app, new_routes)

    if migration:
        call(f'proper db create "{singular_snake if singular else plural_snake}"')
