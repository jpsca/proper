from typing import TYPE_CHECKING

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, call
from ..router.resource import ACTIONS
from .model import gen_model

if TYPE_CHECKING:
    from proper import App


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"
ROUTES_TMPL = "routes.tmpl.py"
FORM_FIELDS = {
    "blob": "File",
    "bool": "Boolean",
    "date": "Date",
    "datetime": "DateTime",
    "decimal": "Float",
    "float": "Float",
    "int": "Integer",
    "decimal": "Float",
    "str": "Text",
    "text": "Text",
    "time": "Time",
    "uuid": "Text",
}
FORM_RENDER_AS = {
    "blob": "textarea",
    "bool": "checkbox",
    "text": "textarea",
}
FORM_DEFAULT_RENDER_AS = "input"
FORM_INPUT_TYPES = {
    "date": "date",
    "datetime": "datetime-local",
    "decimal": "number",
    "float": "number",
    "int": "number",
    "time": "time",
}
FORM_DEFAULT_INPUT_TYPE = "text"


def gen_resource(
    app: "App",
    name: str,
    *attrs: str,
    only: str = "",
    exclude: str = "",
    singular: bool = False,
    migration: bool = False,
) -> None:
    """Stubs out a new resource
    including a controller, model, migration, components, and a resource route
    in the `routes.py` file.

    Use `--migration` to also generate a migration for creating the table.


        proper g resource NAME
            [--only=action[,action]] [--exclude=action[,action]] [--singular]

    Arguments:

    - name: The PascalCased resource name (plural unless is singular).
    - only: Optional comma-separated list of actions to include,
        instead of using the full set.)
    - exclude: Optional comma-separated lists of actions to NOT include
        from the full set of actions.
    - singular [False]: Wether the resource is just one.
    - attrs: Optional list of columns to add to the schema of the resource.

    Attribute pairs are field:type arguments specifying the model's attributes,
    and follows the same syntax of the model generator.
    Run `proper g model --help` for instructions.

    By default it generates the full set of REST actions ("index", "new", "create",
    "show", "edit", "update", and "delete"), but you can choose only some of these
    or to exclude a few by using the optional `only` and `exclude` arguments.

    Sometimes, you have a resource that clients always look up without
    referencing an ID. In this case, you can use `singular=True` to build a
    set of REST routes without `:pk`.

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
    controller_snake = singular_snake if singular else plural_snake
    controller_pascal = singular_pascal if singular else plural_pascal

    only_list = [ac for ac in list(dict.fromkeys(only.split(","))) if ac in ACTIONS]
    exclude_list = [ac for ac in list(dict.fromkeys(exclude.split(","))) if ac in ACTIONS]

    actions = set(ACTIONS)
    if only_list:
        actions = actions.intersection(set(only_list))
    elif exclude_list:
        actions = actions.difference(set(exclude_list))
    if singular:
        actions.remove("index")

    ignored_actions = set(ACTIONS).difference(actions)
    ignored_components = []
    for action in ignored_actions:
        action_pascal = inflection.camelize(action)
        ignored_components.append(
            f"*{action_pascal}.tmpl.jinja",
        )

    attrs_tuples = gen_model(
        app,
        name,
        *attrs,
        singular_pascal=singular_pascal,
        singular_snake=singular_snake,
        plural_snake=plural_snake,
    )
    form_fields = [
        {
            "fclass": FORM_FIELDS[ftype],
            "name": name,
            "render_as": FORM_RENDER_AS.get(ftype, FORM_DEFAULT_RENDER_AS),
            "input_type": FORM_INPUT_TYPES.get(ftype, FORM_DEFAULT_INPUT_TYPE),
            "required": None if "null=True" in options else True
        }
        for name, ftype, options in attrs_tuples
        if ftype in FORM_FIELDS
    ]

    bp = BlueprintRender(
        RESOURCE_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "plural_pascal": plural_pascal,
            "plural_snake": plural_snake,
            "singular_pascal": singular_pascal,
            "singular_snake": singular_snake,
            "controller_snake": controller_snake,
            "controller_pascal": controller_pascal,
            "only": only_list,
            "exclude": exclude_list,
            "actions": actions,
            "singular": singular,
            "form_fields": form_fields,
            "form_class": f"{singular_pascal}Form",
            "load_method": f"_load_{singular_snake}",
            "object": f"self.{singular_snake}",
        },
        ignore=[ROUTES_TMPL] + ignored_components,
    )
    bp()

    routes_tmpl = RESOURCE_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)

    if migration:
        call(f'proper db revision "Create {plural_snake} table"')
