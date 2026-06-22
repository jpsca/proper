from typing import TYPE_CHECKING

import inflection
from hecto import COLORS, printf

from .. import metadata
from ..constants import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_SHOW,
    ACTION_UPDATE,
)
from ..helpers import BLUEPRINTS
from ..helpers.render import render_blueprint, sort_imports_in
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

# A state change is its own resource: `create` makes it happen, `delete`
# undoes it. These are the actions a `parent/child` controller gets by default.
STATE_CHANGE_ACTIONS = (ACTION_CREATE, ACTION_DELETE)


def gen_controller(
    app: "App",
    name: str,
    *attrs: str,
    only: str = "",
    exclude: str = "",
    namespace: str = "",
    pk: str = "",
    singular: bool = False,
    force: bool = False,
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

        force [False]:
            Whether to overwrite existing files without asking.

        attrs:
            Optional list of `field:type` columns for the form schema.
            Uses the same syntax as the model generator.
            Run `proper g model --help` for more information.


    "show", "edit", "update", and "delete"). You can opt for a subset of these
    or exclude specific ones using the `only` and `exclude` arguments.

    For resources that users always look up without an ID, use `singular=True`
    to create REST routes that do not include `:object_id`.

    A `PARENT/CHILD` name (e.g. `card/closure`) scaffolds a state change as its
    own nested resource: a `pk=None` controller mounted under the parent, with
    `create` (make it happen) and `delete` (undo it) stubs, plus a shared
    `ParentScoped` concern that loads the parent record. No form or views are
    created, since a state change redirects rather than rendering a form.

    Examples:

        proper g controller Post
        proper g controller Post --namespace=admin
        proper g controller Post --only=index,show title:str
        proper g controller Post title:str body:text published:bool
        proper g controller Profile --singular
        proper g controller card/closure
        proper g controller card/not_now --only=create

    """
    name_pascal = _name_pascal or inflection.camelize(name)
    name_snake = _name_snake or inflection.underscore(name)
    plural_snake = inflection.pluralize(name_snake)
    name_human = inflection.humanize(name_snake).lower()
    plural_human = inflection.humanize(plural_snake).lower()

    if "/" in name:
        _gen_state_change(app, name, only=only, exclude=exclude, force=force)
        return

    pk = pk.strip().strip(":")

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

    test_client = "signed_client" if metadata.is_installed(app, "auth") else "client"

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
        "nsprefix": nsprefix,
        "test_client": test_client,
    }

    if namespace:
        controllers_init = app.root_path / "controllers" / "__init__.py"
        ns_controllers = app.root_path / "controllers" / namespace
        ns_forms = app.root_path / "forms" / namespace
        ns_views = app.root_path / "views" / namespace

        render_blueprint(
            RESOURCE_BLUEPRINT / "[[app_name]]" / "controllers",
            ns_controllers,
            context=context,
            ignore=ignored_views,
            force=force,
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
            force=force,
        )
        (ns_forms / "__init__.py").touch()

        render_blueprint(
            RESOURCE_BLUEPRINT / "[[app_name]]" / "views",
            ns_views,
            context=context,
            ignore=ignored_views,
            force=force,
        )

    else:
        render_blueprint(
            RESOURCE_BLUEPRINT,
            app.root_path.parent,
            context=context,
            ignore=ignored_views,
            force=force,
        )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)


def _gen_state_change(
    app: "App",
    name: str,
    *,
    only: str = "",
    exclude: str = "",
    force: bool = False,
) -> None:
    """Scaffold a state change as its own nested resource (`parent/child`).

    Creates `controllers/PARENT/CHILD_controller.py` (a `pk=None` resource
    mounted under the parent's URL), a shared `PARENT_scoped.py` concern that
    loads the parent (only if it doesn't exist yet), and a matching test. The
    new controller is wired into `controllers/__init__.py`.
    """
    parent, _, child = name.partition("/")

    parent_snake = inflection.underscore(parent)
    parent_pascal = inflection.camelize(parent_snake)
    parent_plural = inflection.pluralize(parent_snake)
    parent_id = f"{parent_snake}_id"

    child_snake = inflection.underscore(child)
    child_pascal = inflection.camelize(child_snake)
    child_path = inflection.dasherize(child_snake)

    concern_module = f"{parent_snake}_scoped"
    concern_class = f"{parent_pascal}Scoped"
    path = f"{parent_plural}/:{parent_id}/{child_path}"

    only_list = [ac for ac in dict.fromkeys(only.split(",")) if ac in ACTIONS]
    exclude_list = [ac for ac in dict.fromkeys(exclude.split(",")) if ac in ACTIONS]
    actions = set(STATE_CHANGE_ACTIONS)
    if only_list:
        actions = actions.intersection(only_list)
    elif exclude_list:
        actions = actions.difference(exclude_list)

    controllers = app.root_path / "controllers"
    parent_dir = controllers / parent_snake
    concerns_dir = controllers / "concerns"
    parent_dir.mkdir(parents=True, exist_ok=True)
    concerns_dir.mkdir(parents=True, exist_ok=True)
    _touch_init(parent_dir)
    _touch_init(concerns_dir)

    # The concern is shared across every child controller of this parent, so
    # never clobber it: write it only when it doesn't exist yet.
    _write_file(
        concerns_dir / f"{concern_module}.py",
        _state_change_concern_py(
            parent_pascal=parent_pascal,
            parent_snake=parent_snake,
            parent_id=parent_id,
        ),
        force=False,
    )

    _write_file(
        parent_dir / f"{child_snake}_controller.py",
        _state_change_controller_py(
            path=path,
            child_pascal=child_pascal,
            concern_module=concern_module,
            concern_class=concern_class,
            parent_snake=parent_snake,
            parent_pascal=parent_pascal,
            actions=actions,
        ),
        force=force,
    )

    test_client = "signed_client" if metadata.is_installed(app, "auth") else "client"
    test_path = app.root_path.parent / "tests" / "controllers" / f"test_{child_snake}.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    _write_file(
        test_path,
        _state_change_test_py(
            app_name=app.name,
            test_client=test_client,
            child_snake=child_snake,
            child_pascal=child_pascal,
            parent_snake=parent_snake,
            parent_pascal=parent_pascal,
            actions=actions,
        ),
        force=force,
    )

    root_init = controllers / "__init__.py"
    _append_import(root_init, f"from .{parent_snake} import {child_snake}_controller  # noqa")
    sort_imports_in(root_init)


def _touch_init(directory) -> None:
    init = directory / "__init__.py"
    if not init.exists():
        init.write_text("")
        printf("create", str(init), color=COLORS.GREEN)


def _write_file(path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        printf("skip", str(path), color=COLORS.YELLOW)
        return
    verb = "force" if path.exists() else "create"
    path.write_text(content)
    printf(verb, str(path), color=COLORS.GREEN)


def _append_import(init_path, line: str) -> None:
    text = init_path.read_text() if init_path.exists() else ""
    if line in text:
        return
    init_path.write_text(f"{text.rstrip()}\n{line}\n".lstrip("\n"))


def _state_change_concern_py(*, parent_pascal: str, parent_snake: str, parent_id: str) -> str:
    return f"""from proper import Concern
from proper.errors import NotFound

from ...models import {parent_pascal}


class {parent_pascal}Scoped(Concern):
    before = {{"do": "set_{parent_snake}"}}

    def set_{parent_snake}(self):
        {parent_id} = self.params.get("{parent_id}")
        if {parent_id}:
            self.{parent_snake} = {parent_pascal}.get_or_none(id=int({parent_id}))
            if self.request.matched_action != "delete" and not self.{parent_snake}:
                raise NotFound
"""


def _state_change_controller_py(
    *,
    path: str,
    child_pascal: str,
    concern_module: str,
    concern_class: str,
    parent_snake: str,
    parent_pascal: str,
    actions: set[str],
) -> str:
    head = (
        "from ...router import router\n"
        "from ..app_controller import AppController\n"
        f"from ..concerns.{concern_module} import {concern_class}\n"
        "\n\n"
        f'@router.resource("{path}", pk=None)\n'
        f"class {child_pascal}Controller({concern_class}, AppController):\n"
    )
    body = []
    if ACTION_CREATE in actions:
        body.append(
            f"\n    # POST /{path}\n"
            "    def create(self):\n"
            f"        # TODO: apply the state change to self.{parent_snake}\n"
            f'        self.response.redirect_to("{parent_pascal}.show", self.{parent_snake}, flash="...")\n'
        )
    if ACTION_DELETE in actions:
        body.append(
            f"\n    # DELETE /{path}\n"
            "    def delete(self):\n"
            f"        # TODO: undo the state change on self.{parent_snake}\n"
            f'        self.response.redirect_to("{parent_pascal}.show", self.{parent_snake})\n'
        )
    if not body:
        body.append("    pass\n")
    return head + "".join(body)


def _state_change_test_py(
    *,
    app_name: str,
    test_client: str,
    child_snake: str,
    child_pascal: str,
    parent_snake: str,
    parent_pascal: str,
    actions: set[str],
) -> str:
    blocks = []
    if ACTION_CREATE in actions:
        blocks.append(
            f"def test_{child_snake}_create({test_client}):\n"
            f"    # {parent_snake} = {parent_pascal}.create( ... )\n"
            f'    # url = app.url_for("{child_pascal}.create", {_parent_id_kw(parent_snake)})\n'
            f"    # response = {test_client}.post(url)\n"
            "    # assert response.status == 303\n"
            "    pass\n"
        )
    if ACTION_DELETE in actions:
        blocks.append(
            f"def test_{child_snake}_delete({test_client}):\n"
            f"    # {parent_snake} = {parent_pascal}.create( ... )\n"
            f'    # url = app.url_for("{child_pascal}.delete", {_parent_id_kw(parent_snake)})\n'
            f"    # response = {test_client}.delete(url)\n"
            "    # assert response.status == 303\n"
            "    pass\n"
        )
    return f"from {app_name}.main import app\n\n\n" + "\n\n".join(blocks)


def _parent_id_kw(parent_snake: str) -> str:
    return f"{parent_snake}_id={parent_snake}.id"
