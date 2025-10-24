from proper.errors import NotFound
from proper.status import unprocessable

from .app import AppController
from app.models import [[ name_pascal ]]
from app.forms.[[ name_snake ]] import [[ form_class ]]
from app.router import router


@router.resource("[[ name_snake ]]")
class [[ name_pascal ]]Controller(AppController):
    [% if "index" in actions -%]
    def index(self):
        self.[[ name_snake ]] = [[ name_pascal ]]/select()
        return self.render("pages/[[ name_snake ]]/index.jinja")
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        self.[[ load_method ]]()
        return self.render("pages/[[ name_snake ]]/show.jinja")
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        self.form = [[ form_class ]].as_form()
        return self.render("pages/[[ name_snake ]]/new.jinja")
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(object=[[ object ]])
        return self.render("pages/[[ name_snake ]]/edit.jinja")
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        self.form = [[ form_class ]].as_form(self.params)
        if self.form.is_invalid:
            return self.render("pages/[[ name_snake ]]/new.jinja", status=unprocessable)

        [[ name_snake ]] = self.form.save()
        [% if parent %]
        [[ name_snake ]].[[ parent_name_snake ]] = [[ parent ]]
        [% endif -%]
        [[ name_snake ]].save()
        self.response.redirect_to(
            "[[ name_pascal ]].show",
            pk=[[ name_snake ]].id,
            flash="[[ name_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(self.params, object=[[ object ]])
        if self.form.is_invalid:
            return self.render("pages/[[ name_snake ]]/edit.jinja", status=unprocessable)

        [[ name_snake ]] = self.form.save()
        [[ name_snake ]].save()
        self.response.redirect_to(
            "[[ name_pascal ]].show",
            pk=[[ object ]].id,
            flash="[[ name_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        self.[[ load_method ]](not_found=False)
        if [[ object ]]:  # deleting twice does not fail
            [[ object ]].delete_instance()
        self.response.redirect_to(
            "[[ name_pascal ]].index",
            flash="[[ name_pascal ]] was deleted",
        )
[% endif %]
    [% if "restore" in actions -%]
    def restore(self):
        self.[[ load_method ]]()
        self.response.redirect_to(
            "[[ name_pascal ]].index",
            flash="[[ name_pascal ]] was restored",
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
        [[ object ]] = [[ name_pascal ]]/get_or_none()
        [% elif parent -%]
        [[ object_id ]] = self.params.get("pk")

        [[ object ]] = [[ name_pascal ]]/get_or_none(
            ([[ name_pascal ]]/[[ parent_id ]] == [[ parent ]].id) &
            ([[ name_pascal ]]/id == [[ object_id ]])
        )
        [% else -%]
        [[ object_id ]] = self.params.get("pk")

        [[ object ]] = [[ name_pascal ]]/get_or_none([[ object_id ]])
        [% endif -%]
        if not_found and not [[ object ]]:
            raise NotFound
[%- endif %]
