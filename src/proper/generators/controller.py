from typing import TYPE_CHECKING

import inflection

from ..helpers import BLUEPRINTS
from ..helpers.render import render_blueprint, sort_imports_in
from ..router import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_SHOW,
    ACTION_UPDATE,
)
from .model import _split_attr


if TYPE_CHECKING:
    from ..app import App


RESOURCE_BLUEPRINT = BLUEPRINTS / "controller"

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

RENDER_METHODS = {
    "bigint": "number_input",
    "bool": "checkbox",
    "date": "date_input",
    "datetime": "datetime_input",
    "decimal": "number_input",
    "float": "number_input",
    "int": "number_input",
    "str": "text_input",
    "text": "textarea",
    "time": "time_input",
    "uuid": "text_input",
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


def gen_controller(
    app: "App",
    name: str,
    *attrs: str,
    only: str = "",
    exclude: str = "",
    namespace: str = "",
    pk: str = "",
    singular: bool = False,
    _name_pascal: str = "",
    _name_snake: str = "",
) -> None:
    """Stubs out a new controller including views and a form.

    proper g controller NAME
        [--only=action[,action]] [--exclude=action[,action]]
        [--namespace=NS_NAME] [--pk=object_id] [--singular]
        [attrs...]

    Arguments:
        name:
            The PascalCased resource name.

        only:
            Optional comma-separated list of actions to include,
            instead of the full set.

        exclude:
            Optional comma-separated list of actions to exclude
            from the full set.

        namespace:
            Optional namespace for the new controller, e.g.: "admin".
            Will be used as the name of the subfolder.

        pk:
            Optional name for the `:object_id` parameter
            (defaults to empty, so `[name_snakecased]_id` will be used
            in the generated URLs). Ignored if `singular` is `True`.

        singular [False]:
            Whether the resource represents a single entity for the user (like "profile").

        attrs:
            Optional list of `field:type` columns for the form schema.
            Uses the same syntax as the model generator.
            Run `proper g model --help` for more information.


    "show", "edit", "update", and "delete"). You can opt for a subset of these
    or exclude specific ones using the `only` and `exclude` arguments.

    For resources that users always look up without an ID, use `singular=True`
    to create REST routes that do not include `:object_id`.

    Examples:

        proper g controller Post
        proper g controller Post --namespace=admin
        proper g controller Post --only=index,show title:str
        proper g controller Post title:str body:text published:bool
        proper g controller Profile --singular

    """
    pk = pk.strip().strip(":")

    name_pascal = _name_pascal or inflection.camelize(name)
    name_snake = _name_snake or inflection.underscore(name)
    plural_snake = inflection.pluralize(name_snake)
    name_human = inflection.humanize(name_snake).lower()
    plural_human = inflection.humanize(plural_snake).lower()

    only_list = [ac for ac in list(dict.fromkeys(only.split(","))) if ac in ACTIONS]
    exclude_list = [ac for ac in list(dict.fromkeys(exclude.split(","))) if ac in ACTIONS]

    actions: set[str] = set(ACTIONS)
    if only_list:
        actions = actions.intersection(set(only_list))
    elif exclude_list:
        actions = actions.difference(set(exclude_list))
    if singular:
        actions.discard("index")

    ignored_actions = set(ACTIONS).difference(actions)
    ignored_views = []
    for action in ignored_actions:
        ignored_views.append(
            f"*{action}.tt.jx",
        )

    attrs_tuples = attrs_tuples = [_split_attr(attr) for attr in attrs]
    form_fields = [
        {
            "type": FORM_FIELDS[ftype],
            "name": name,
            "default": None,
        }
        for name, ftype, _options in attrs_tuples
        if ftype in FORM_FIELDS
    ]

    render_fields = [
        {
            "method": RENDER_METHODS[ftype],
            "name": name,
            "label": inflection.humanize(name),
        }
        for name, ftype, _options in attrs_tuples
        if ftype in RENDER_METHODS
    ]

    nsprefix = ""
    if namespace:
        nsprefix = ":".join(inflection.camelize(seg) for seg in namespace.split("/")) + ":"

    context = {
        "app_name": app.name,
        "name_pascal": name_pascal,
        "name_snake": name_snake,
        "name_human": name_human,
        "plural_snake": plural_snake,
        "plural_human": plural_human,
        "only": only_list,
        "exclude": exclude_list,
        "actions": actions,
        "singular": singular,
        "form_fields": form_fields,
        "render_fields": render_fields,
        "form_class": f"{name_pascal}Form",
        "load_method": f"set_{name_snake}",
        "object_id": pk or f"{name_snake}_id",
        "pk": pk,
        "namespace": namespace,
        "nsprefix": nsprefix
    }

    if namespace:
        controllers_init = app.root_path / "controllers" / "__init__.py"
        ns_controllers = app.root_path / "controllers" / namespace
        ns_forms = app.root_path / "forms" / namespace
        ns_views = app.root_path / "views" / "pages" / namespace

        render_blueprint(
            RESOURCE_BLUEPRINT / "[[app_name]]" / "controllers",
            ns_controllers,
            context=context,
            ignore=ignored_views,
        )

        # Overwrite the contents of the rendered __init__
        (ns_controllers / "__init__.py").write_text("")

        # Append to root controllers __init__
        controllers_init.write_text(
            controllers_init.read_text() +
            f"\nfrom .{namespace} import {name_snake}_controller  # noqa"
        )

        render_blueprint(
            RESOURCE_BLUEPRINT / "[[app_name]]" / "forms",
            ns_forms,
            context=context,
            ignore=ignored_views,
        )
        (ns_forms / "__init__.py").touch()

        render_blueprint(
            RESOURCE_BLUEPRINT / "[[app_name]]" / "views" / "pages",
            ns_views,
            context=context,
            ignore=ignored_views,
        )

    else:
        render_blueprint(
            RESOURCE_BLUEPRINT,
            app.root_path.parent,
            context=context,
            ignore=ignored_views,
        )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)
