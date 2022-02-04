from proper import status
from proper.errors import NotFound

from [[ app_name ]].models import [[ singular_pascal ]], db
from ..application import ApplicationController
from .forms import [[ singular_pascal ]]Form


class [[ controller_pascal ]](ApplicationController):

    [% if "index" in actions -%]
    def index(self):
        "GET /[[ plural_snake ]]"
        self.[[ plural_snake ]] = db.s.all([[ singular_pascal ]])
    [%- endif %]

    [% if "new" in actions -%]
    def new(self):
        "GET /[[ plural_snake ]]/new"
        self.form = [[ singular_pascal ]]Form()
    [%- endif %]

    [% if "create" in actions -%]
    def create(self):
        "POST /[[ plural_snake ]]"
        self.form = [[ singular_pascal ]]Form(self.req.form)
        if not self.form.validate():
            self.resp.template = "new"
            self.resp.status_code = status.unprocessable_entity
            return

        [[ singular_snake ]] = self.form.save()
        db.s.add([[ singular_snake ]])
        db.s.commit()
        self.resp.flash("[[ singular_pascal ]] created")
        self.resp.redirect_to("[[ plural_pascal ]].show", pk=[[ singular_snake ]].id)
    [%- endif %]

    [% if "show" in actions -%]
    def show(self[% if not singular %], pk[% endif %]):
        "GET /[[ plural_snake ]]/1"
        self._load_[[ singular_snake ]]([% if not singular %]pk[% endif %])
    [%- endif %]

    [% if "edit" in actions -%]
    def edit(self[% if not singular %], pk[% endif %]):
        "GET /[[ plural_snake ]]/1/edit"
        self._load_[[ singular_snake ]]([% if not singular %]pk[% endif %])
        self.form = [[ singular_pascal ]]Form(object=self.[[ singular_snake ]])
    [%- endif %]

    [% if "update" in actions -%]
    def update(self[% if not singular %], pk[% endif %]):
        "PATCH/PUT /[[ plural_snake ]]/1"
        self._load_[[ singular_snake ]]([% if not singular %]pk[% endif %])
        self.form = [[ singular_pascal ]]Form(self.req.form, object=self.[[ singular_snake ]])
        if not self.form.validate():
            self.resp.template = "edit"
            self.resp.status_code = status.unprocessable_entity
            return

        self.form.save()
        db.s.commit()
        self.resp.flash("[[ singular_pascal ]] updated")
        self.resp.redirect_to("[[ plural_pascal ]].show", pk=pk)
    [%- endif %]

    [% if "delete" in actions -%]
    def delete(self[% if not singular %], pk[% endif %]):
        "DELETE /[[ plural_snake ]]/1"
        [[ singular_snake ]] = db.s.get([[ singular_pascal ]], pk)
        if [[ singular_snake ]]:  # deleting twice does not fail
            db.s.delete([[ singular_snake ]])
            db.s.commit()
        self.resp.flash("[[ singular_pascal ]] deleted")
        self.resp.redirect_to("[[ plural_pascal ]].index")
    [%- endif %]

    # Private

    def _load_[[ singular_snake ]](self[% if not singular %], pk[% endif %]):
        self.[[ singular_snake ]] = db.s.get([[ singular_pascal ]], pk)
        if not self.[[ singular_snake ]]:
            raise NotFound
