from proper import request, response  # noqa
from proper.errors import NotFound
from proper.status import unprocessable

from [[ app_name ]].models import [[ singular_pascal ]], db
from ..application import AppController
from .forms import [[ singular_pascal ]]Form


class [[ controller_pascal ]](AppController):
    [% if "index" in actions -%]
    def index(self):
        """GET /[[ plural_snake ]]"""
        self.[[ plural_snake ]] = db.s.all([[ singular_pascal ]])
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        """GET /[[ plural_snake ]]/1"""
        self._load_[[ singular_snake ]]()
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        """GET /[[ plural_snake ]]/new"""
        self.form = [[ singular_pascal ]]Form()
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        """GET /[[ plural_snake ]]/1/edit"""
        self._load_[[ singular_snake ]]()
        self.form = [[ singular_pascal ]]Form(object=self.[[ singular_snake ]])
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        """POST /[[ plural_snake ]]"""
        self.form = [[ singular_pascal ]]Form(self.params)
        if not self.form.validate():
            return self.render("[[ plural_snake ]]/new", status=unprocessable)

        [[ singular_snake ]] = self.form.save()
        db.s.add([[ singular_snake ]])
        db.s.commit()
        response.redirect_to(
            "[[ plural_pascal ]].show", pk=self.[[ singular_snake ]].id,
            flash="[[ singular_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        """PATCH|PUT /[[ plural_snake ]]/1"""
        self._load_[[ singular_snake ]]()
        self.form = [[ singular_pascal ]]Form(self.params, object=self.[[ singular_snake ]])
        if not self.form.validate():
            return self.render("[[ plural_snake ]]/edit", status=unprocessable)

        self.form.save()
        db.s.commit()
        response.redirect_to(
            "[[ plural_pascal ]].show", pk=self.[[ singular_snake ]].id,
            flash="[[ singular_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        """DELETE /[[ plural_snake ]]/1"""
        self._load_[[ singular_snake ]](not_found=False)
        if self.[[ singular_snake ]]:  # deleting twice does not fail
            db.s.delete(self.[[ singular_snake ]])
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

    def _load_[[ singular_snake ]](self, not_found=True):
        [% if singular -%]
        self.[[ singular_snake ]] = db.s.first([[ singular_pascal ]])
        [% else -%]
        self.[[ singular_snake ]] = db.s.get([[ singular_pascal ]], self.params["pk"])
        [% endif -%]
        if not_found and not self.[[ singular_snake ]]:
            raise NotFound
[%- endif %]
