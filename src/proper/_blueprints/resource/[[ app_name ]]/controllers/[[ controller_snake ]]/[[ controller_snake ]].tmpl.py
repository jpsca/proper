from proper import request, response  # noqa
from proper.errors import NotFound
from proper.status import unprocessable

from [[ app_name ]].models import [[ singular_pascal ]], db
from ..app import AppController
from .forms import [[ form_class ]]


class [[ controller_pascal ]](AppController):
    [% if "index" in actions -%]
    def index(self):
        """GET /[[ plural_snake ]]"""
        self.[[ plural_snake ]] = db.s.all([[ singular_pascal ]])
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        """GET /[[ plural_snake ]]/1"""
        self.[[ load_method ]]()
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        """GET /[[ plural_snake ]]/new"""
        self.form = [[ form_class ]]()
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        """GET /[[ plural_snake ]]/1/edit"""
        self.[[ load_method ]]()
        self.form = [[ form_class ]](object=[[ object ]])
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        """POST /[[ plural_snake ]]"""
        self.form = [[ form_class ]](self.params)
        if not self.form.validate():
            return self.render("[[ controller_pascal ]].New", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        db.s.add([[ singular_snake ]])
        db.s.commit()
        response.redirect_to(
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
            return self.render("[[ controller_pascal ]].Edit", status=unprocessable)

        self.form.save()
        db.s.commit()
        response.redirect_to(
            "[[ plural_pascal ]].show", pk=[[ object ]].id,
            flash="[[ singular_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        """DELETE /[[ plural_snake ]]/1"""
        self.[[ load_method ]](not_found=False)
        if [[ object ]]:  # deleting twice does not fail
            db.s.delete([[ object ]])
            db.s.commit()
        response.redirect_to(
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
        [[ object ]] = db.s.first([[ singular_pascal ]])
        [% else -%]
        [[ object ]] = db.s.get([[ singular_pascal ]], self.params["pk"])
        [% endif -%]
        if not_found and not [[ object ]]:
            raise NotFound
[%- endif %]
