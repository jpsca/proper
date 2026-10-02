[% set has_member = "show" in actions or "edit" in actions or "update" in actions or "delete" in actions -%]
[% set has_load = has_member and (has_model or not singular) -%]
[% set has_form = "new" in actions or "edit" in actions or "create" in actions or "update" in actions -%]
[% set has_validate = "create" in actions or "update" in actions -%]
[% if has_load and has_model -%]
from proper.errors import NotFound

[% endif -%]
[% if has_form -%]
[% if namespace -%]
from [[app_name]].forms.[[namespace]].[[name_snake]] import [[form_class]]
[% else -%]
from [[app_name]].forms.[[name_snake]] import [[form_class]]
[% endif -%]
[% endif -%]
[% if has_model -%]
from [[app_name]].models import [[name_pascal]]
[% endif -%]
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
    [% if not actions -%]
    pass

    [% endif -%]
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
        [% if has_model -%]
        self.[[plural_snake]] = [[name_pascal]].select()
        [%- else -%]
        pass
        [%- endif %]

    [% endif -%]
    [% if "show" in actions -%]
    def show(self):
        pass

    [% endif -%]
    [% if "new" in actions -%]
    def new(self):
        pass

    [% endif -%]
    [% if "edit" in actions -%]
    def edit(self):
        pass

    [% endif -%]
    [% if "create" in actions -%]
    def create(self):
        [% if has_model -%]
        [[name_snake]] = self.form.save()
        [%- else -%]
        # TODO: `data` is a dict with the values of the form
        data = self.form.save()  # noqa: F841
        [%- endif %]
        self.response.redirect_to([[after_save]], flash="[[name_pascal]] was created")

    [% endif -%]
    [% if "update" in actions -%]
    def update(self):
        [% if has_model -%]
        [[name_snake]] = self.form.save()
        [%- else -%]
        # TODO: `data` is a dict with the values of the form
        data = self.form.save()  # noqa: F841
        [%- endif %]
        self.response.redirect_to([[after_save]], flash="[[name_pascal]] was updated")

    [% endif -%]
    [% if "delete" in actions -%]
    def delete(self):
        [% if has_model -%]
        if self.[[name_snake]]:  # deleting twice does not fail
            self.[[name_snake]].delete_instance()
        [%- else -%]
        # TODO: delete it. Deleting twice should not fail
        [%- endif %]
        self.response.redirect_to([[after_delete]], flash="[[name_pascal]] was deleted")

    [% endif -%]
    [% if has_load or has_form -%]
    # Private
    [%- endif %]
    [%- if has_load %]

    def [[load_method]](self):
        [% if not has_model -%]
        # TODO: load the record, and raise `NotFound` if it doesn't exist
        self.[[object_id]] = self.params.get("[[object_id]]", "")
        [%- elif singular -%]
        self.[[name_snake]] = [[name_pascal]].get_or_none()
        if self.request.matched_action != "delete" and not self.[[name_snake]]:
            raise NotFound
        [%- else -%]
        [[object_id]] = self.params.get("[[object_id]]", "")
        self.[[name_snake]] = [[name_pascal]].find(int([[object_id]]))
        if self.request.matched_action != "delete" and not self.[[name_snake]]:
            raise NotFound
        [%- endif %]
    [%- endif %]
    [%- if has_form %]

    def set_form(self):
        [% if has_load and has_model -%]
        obj = getattr(self, "[[name_snake]]", None)
        self.form = [[form_class]](self.params, object=obj)
        [%- else -%]
        self.form = [[form_class]](self.params)
        [%- endif %]
    [%- endif %]
