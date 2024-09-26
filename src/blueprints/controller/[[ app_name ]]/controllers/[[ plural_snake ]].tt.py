from proper.errors import NotFound
from proper.status import unprocessable

from [[ app_name ]].models import [[ singular_pascal ]]
from [[ app_name ]].forms.[[ plural_snake ]] import [[ form_class ]]
from .app import AppController


@router.resource("[[ plural_snake ]]")
class [[ plural_pascal ]](AppController):
    [% if "index" in actions -%]
    def index(self):
        self.[[ plural_snake ]] = [[ singular_pascal ]].select()
        return self.render("[[ singular_pascal ]].Index")
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        self.[[ load_method ]]()
        return self.render("[[ singular_pascal ]].Show")
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        self.form = [[ form_class ]].as_form()
        return self.render("[[ singular_pascal ]].New")
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(object=[[ object ]])
        return self.render("[[ singular_pascal ]].Edit")
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        self.form = [[ form_class ]].as_form(self.params)
        if self.form.is_invalid:
            return self.render("[[ singular_pascal ]].New", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [% if parent %]
        [[ singular_snake ]].[[ parent_singular_snake ]] = [[ parent ]]
        [% endif -%]
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show",
            pk=[[ singular_snake ]].id,
            flash="[[ singular_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(self.params, object=[[ object ]])
        if self.form.is_invalid:
            return self.render("[[ singular_pascal ]].Edit", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show",
            pk=[[ object ]].id,
            flash="[[ singular_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        self.[[ load_method ]](not_found=False)
        if [[ object ]]:  # deleting twice does not fail
            [[ object ]].delete_instance()
        self.response.redirect_to(
            "[[ plural_pascal ]].index",
            flash="[[ singular_pascal ]] was deleted",
        )
[% endif %]
    [% if "restore" in actions -%]
    def restore(self):
        self.[[ load_method ]]()
        self.response.redirect_to(
            "[[ plural_pascal ]].index",
            flash="[[ singular_pascal ]] was restored",
        )
[% endif %]
    # Private

    [% if
      "show" in actions
      or "edit" in actions
      or "update" in actions
      or "delete" in actions
    -%]
    def [[ load_method ]](self, not_found=True):
        [% if singular -%]
        [[ object ]] = [[ singular_pascal ]].get_or_none()
        [% elif parent -%]
        [[ object_id ]] = self.params.get("pk")

        [[ object ]] = [[ singular_pascal ]].get_or_none(
            ([[ singular_pascal ]].[[ parent_id ]] == [[ parent ]].id) &
            ([[ singular_pascal ]].id == [[ object_id ]])
        )
        [% else -%]
        [[ object_id ]] = self.params.get("pk")

        [[ object ]] = [[ singular_pascal ]].get_or_none(
            [[ singular_pascal ]].id == [[ object_id ]]
        )
        [% endif -%]
        if not_found and not [[ object ]]:
            raise NotFound
[%- endif %]
