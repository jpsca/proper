[% set has_member = "show" in actions or "edit" in actions or "update" in actions or "delete" in actions -%]
[% set has_load = has_member and (has_model or not singular) -%]
[% set has_form = "new" in actions or "edit" in actions or "create" in actions or "update" in actions -%]
[% set has_loader = has_load and has_model -%]
[% set needs_404 = has_loader and ("show" in actions or "edit" in actions or "update" in actions) -%]
[% if needs_404 -%]
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
        [% if has_loader -%]
        self.[[load_method]]()
        if not self.[[name_snake]]:
            raise NotFound
        [%- elif has_load -%]
        # TODO: load the record, and raise `NotFound` if it doesn't exist
        self.[[object_id]] = self.params.get("[[object_id]]", "")
        [%- else -%]
        pass
        [%- endif %]

    [% endif -%]
    [% if "new" in actions -%]
    def new(self):
        self.form = [[form_class]](self.params)

    [% endif -%]
    [% if "create" in actions -%]
    def create(self):
        self.form = [[form_class]](self.params)
        if self.form.is_invalid:
            return self.redo()

        [% if not has_model -%]
        # TODO: `data` is a dict with the values of the form
        data = self.form.save()  # noqa: F841
        [%- elif after_save_object -%]
        [[name_snake]] = self.form.save()
        [%- else -%]
        self.form.save()
        [%- endif %]
        self.response.redirect_to([[after_save]], flash="[[name_pascal]] was created")

    [% endif -%]
    [% if "edit" in actions -%]
    def edit(self):
        [% if has_loader -%]
        self.[[load_method]]()
        if not self.[[name_snake]]:
            raise NotFound

        self.form = [[form_class]](self.params, self.[[name_snake]])
        [%- elif has_load -%]
        # TODO: load the record, and raise `NotFound` if it doesn't exist
        self.[[object_id]] = self.params.get("[[object_id]]", "")
        self.form = [[form_class]](self.params)
        [%- else -%]
        self.form = [[form_class]](self.params)
        [%- endif %]

    [% endif -%]
    [% if "update" in actions -%]
    def update(self):
        [% if has_loader -%]
        self.[[load_method]]()
        if not self.[[name_snake]]:
            raise NotFound

        self.form = [[form_class]](self.params, self.[[name_snake]])
        [%- elif has_load -%]
        # TODO: load the record, and raise `NotFound` if it doesn't exist
        self.[[object_id]] = self.params.get("[[object_id]]", "")
        self.form = [[form_class]](self.params)
        [%- else -%]
        self.form = [[form_class]](self.params)
        [%- endif %]
        if self.form.is_invalid:
            return self.redo()

        [% if not has_model -%]
        # TODO: `data` is a dict with the values of the form
        data = self.form.save()  # noqa: F841
        [%- elif after_save_object -%]
        [[name_snake]] = self.form.save()
        [%- else -%]
        self.form.save()
        [%- endif %]
        self.response.redirect_to([[after_save]], flash="[[name_pascal]] was updated")

    [% endif -%]
    [% if "delete" in actions -%]
    def delete(self):
        [% if has_loader -%]
        self.[[load_method]]()
        if self.[[name_snake]]:
            self.[[name_snake]].delete_instance()
        [%- elif has_load -%]
        self.[[object_id]] = self.params.get("[[object_id]]", "")
        # TODO: delete it. Deleting twice should not fail
        [%- else -%]
        # TODO: delete it. Deleting twice should not fail
        [%- endif %]
        self.response.redirect_to([[after_delete]], flash="[[name_pascal]] was deleted")

    [% endif -%]
    [% if has_loader -%]
    # Private

    def [[load_method]](self):
        [% if singular -%]
        self.[[name_snake]] = [[name_pascal]].get_or_none()
        [%- else -%]
        [[object_id]] = self.params.get("[[object_id]]", "")
        self.[[name_snake]] = [[name_pascal]].find(int([[object_id]])) if [[object_id]].isdigit() else None
        [%- endif %]
    [%- endif %]
