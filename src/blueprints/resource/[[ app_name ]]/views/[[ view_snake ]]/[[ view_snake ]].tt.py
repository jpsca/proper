from proper.errors import NotFound
from proper.status import unprocessable

from [[ app_name ]].models import [[ singular_pascal ]]
    [%- if parent %], [[ parent_singular_pascal ]][% endif %]
from ..app import AppView
from .forms import [[ form_class ]]


class [[ view_pascal ]](AppView):
    [% if parent -%]
    def before(self):
        self.[[ load_parent_method ]]()
[% endif %]
    [% if "index" in actions -%]
    def index(self):
        """GET [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]"""
        self.[[ plural_snake ]] = [[ singular_pascal ]].select()
        return self.render("[[ view_pascal ]].Index")
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        """GET [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
        return self.render("[[ view_pascal ]].Show")
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        """GET [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/new"""
        self.form = [[ form_class ]].as_form()
        return self.render("[[ view_pascal ]].New")
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        """GET [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/1/edit"""
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(object=[[ object ]])
        return self.render("[[ view_pascal ]].Edit")
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        """POST [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]"""
        self.form = [[ form_class ]].as_form(self.params)
        if self.form.is_invalid:
            return self.render("[[ view_pascal ]].New", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [% if parent %]
        [[ singular_snake ]].[[ parent_singular_snake ]] = [[ parent ]]
        [% endif -%]
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show",
            pk=[[ singular_snake ]].id,
            [% if parent %][[ parent_id ]]=[[ parent ]].id,
            [% endif %]flash="[[ singular_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        """PATCH|PUT [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
        self.form = [[ form_class ]].as_form(self.params, object=[[ object ]])
        if self.form.is_invalid:
            return self.render("[[ view_pascal ]].Edit", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show",
            pk=[[ object ]].id,
            [% if parent %][[ parent_id ]]=[[ parent ]].id,
            [% endif %]flash="[[ singular_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        """DELETE [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/1"""
        self.[[ load_method ]](not_found=False)
        if [[ object ]]:  # deleting twice does not fail
            [[ object ]].delete_instance()
        self.response.redirect_to(
            "[[ plural_pascal ]].index",
            [% if parent %][[ parent_id ]]=[[ parent ]].id,
            [% endif %]flash="[[ singular_pascal ]] was deleted",
        )
[% endif %]
    [% if "restore" in actions -%]
    def restore(self):
        """RESTORE [% if parent %]/[[ parent_plural_snake ]]/1[% endif %]/[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
        self.response.redirect_to(
            "[[ plural_pascal ]].index",
            [% if parent %][[ parent_id ]]=[[ parent ]].id,
            [% endif %]flash="[[ singular_pascal ]] was restored",
        )
[% endif %]
    # Private

    [% if parent -%]
    def [[ load_parent_method ]](self):
        [% if singular -%]
        [[ parent ]] = [[ parent_singular_pascal ]].get_or_none()
        [% else -%]
        [[ parent_id ]] = self.params.get("[[ parent_id ]]")

        [[ parent ]] = [[ parent_singular_pascal ]].get_or_none(
            [[ parent_singular_pascal ]].id == [[ parent_id ]]
        )
        [% endif -%]
        if not [[ parent ]]:
            raise NotFound
[% endif %]
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
