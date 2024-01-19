from proper.errors import NotFound
from proper.status import unprocessable

from [[ app_name ]].models import [[ singular_pascal ]]
from ..app import AppView
from .forms import [[ form_class ]]


class [[ view_pascal ]](AppView):
    [% if "index" in actions -%]
    def index(self):
        """GET /[[ plural_snake ]]"""
        self.[[ plural_snake ]] = [[ singular_pascal ]].select()
        return self.render("[[ view_pascal ]].Index")
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        """GET /[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
        return self.render("[[ view_pascal ]].Show")
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        """GET /[[ plural_snake ]]/new"""
        self.form = [[ form_class ]]()
        return self.render("[[ view_pascal ]].New")
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        """GET /[[ plural_snake ]]/1/edit"""
        self.[[ load_method ]]()
        self.form = [[ form_class ]](object=[[ object ]])
        return self.render("[[ view_pascal ]].Edit")
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        """POST /[[ plural_snake ]]"""
        self.form = [[ form_class ]](self.params)
        if not self.form.validate():
            return self.render("[[ view_pascal ]].New", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show", pk=[[ singular_snake ]].id,
            flash="[[ singular_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        """PATCH|PUT /[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
        self.form = [[ form_class ]](self.params, object=[[ object ]])
        if not self.form.validate():
            return self.render("[[ view_pascal ]].Edit", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        [[ singular_snake ]].save()
        self.response.redirect_to(
            "[[ plural_pascal ]].show", pk=[[ object ]].id,
            flash="[[ singular_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        """DELETE /[[ plural_snake ]]/1"""
        self.[[ load_method ]](not_found=False)
        if [[ object ]]:  # deleting twice does not fail
            [[ object ]].delete_instance()
        self.response.redirect_to(
            "[[ plural_pascal ]].index",
            flash="[[ singular_pascal ]] was deleted",
        )
[% endif %]
    [% if
      "show" in actions
      or "edit" in actions
      or "update" in actions
      or "delete" in actions
    -%]
    # Private

    def [[ load_method ]](self, not_found=True):
        [% if singular -%]
        [[ object ]] = [[ singular_pascal ]].get_or_none()
        [% else -%]
        [[ object ]] = [[ singular_pascal ]].get_or_none([[ singular_pascal ]].id == self.params.get("pk"))
        [% endif -%]
        if not_found and not [[ object ]]:
            raise NotFound
[%- endif %]
