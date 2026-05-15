[% set has_load = "show" in actions or "edit" in actions or "update" in actions or "delete" in actions -%]
[% set has_form = "new" in actions or "edit" in actions or "create" in actions or "update" in actions -%]
[% set has_validate = "create" in actions or "update" in actions -%]
from proper.errors import NotFound

[% if namespace %]
from [[app_name]].forms.[[namespace]].[[name_snake]] import [[form_class]]
[% else %]
from [[app_name]].forms.[[name_snake]] import [[form_class]]
[% endif -%]
from [[app_name]].models import [[name_pascal]]
[% if namespace -%]
from [[app_name]].router import [[namespace]]_router
from ..app_controller import AppController


@[[namespace]]_router.resource("[[plural_snake]]"
[%- else -%]
from [[app_name]].router import router
from .app_controller import AppController


@router.resource("[[plural_snake]]"
[%- endif %]
    [%- if singular %], pk=None
    [%- elif pk %], pk="[[pk]]"
    [%- endif -%]
)
class [[name_pascal]]Controller(AppController):
    [% if has_load or has_form or has_validate -%]
    before = [
        [%- if has_load %]
        {"do": "[[load_method]]", "exclude": ["index", "new", "create"]},
        [%- endif %]
        [%- if has_form %]
        {"do": "set_form", "exclude": ["index", "show", "delete"]},
        [%- endif %]
        [%- if has_validate %]
        {"do": "validate_form", "only": ["create", "update"]},
        [%- endif %]
    ]

    [% endif -%]
    [% if "index" in actions -%]
    def index(self):
        self.[[plural_snake]] = [[name_pascal]].select()
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        pass
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        pass
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        pass
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        [[name_snake]] = self.form.save()
        [[name_snake]].save()
        self.response.redirect_to("[[nsprefix]][[name_pascal]].show", [[name_snake]], flash="[[name_pascal]] was created")
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        [[name_snake]] = self.form.save()
        [[name_snake]].save()
        self.response.redirect_to("[[nsprefix]][[name_pascal]].show", [[name_snake]], flash="[[name_pascal]] was updated")
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        if self.[[name_snake]]:  # deleting twice does not fail
            self.[[name_snake]].delete_instance()
        self.response.redirect_to("[[nsprefix]][[name_pascal]].index", flash="[[name_pascal]] was deleted")
[% endif %]
    [% if has_load or has_form -%]
    # Private
[% endif %]
    [% if has_load -%]

    def [[load_method]](self):
        [% if singular -%]
        self.[[name_snake]] = [[name_pascal]].get_or_none()
        [% else -%]
        [[object_id]] = self.params.get("[[object_id]]", "")
        self.[[name_snake]] = [[name_pascal]].get_or_none(id=int([[object_id]]))
        [% endif -%]
        if self.request.matched_action != "delete" and not self.[[name_snake]]:
            raise NotFound
[% endif -%]
    [% if has_form %]
    def set_form(self):
        [% if has_load -%]
        obj = getattr(self, "[[name_snake]]", None)
        [% else -%]
        obj = None
        [% endif -%]
        self.form = [[form_class]](self.params, object=obj)
    [% endif -%]
