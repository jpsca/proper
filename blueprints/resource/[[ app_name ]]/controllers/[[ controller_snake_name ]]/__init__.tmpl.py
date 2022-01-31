from proper.errors import NotFound

from [[ app_name ]].models import [[ model_class_name ]], db
from ..application import ApplicationController
from .forms import [[ model_class_name ]]Form


class [[ controller_class_name ]](ApplicationController):

    [% if "index" in actions -%]
    def index(self):
        "GET /[[ controller_snake_name ]]"
        self.[[ controller_snake_name ]] = db.s.all([[ model_class_name ]])
    [%- endif %]

    [% if "new" in actions -%]
    def new(self):
        "GET /[[ controller_snake_name ]]/new"
        self.form = [[ model_class_name ]]Form()
    [%- endif %]

    [% if "create" in actions -%]
    def create(self):
        "POST /[[ controller_snake_name ]]"
        self.form = [[ model_class_name ]]Form(self.req.form)
        if not self.form.validate():
            self.resp.template = "new"
            return

        [[ model_snake_name ]] = self.form.save()
        db.s.add([[ model_snake_name ]])
        db.s.commit()
        self.resp.flash("[[ model_class_name ]] created")
        self.resp.redirect_to("[[ controller_class_name ]].show", pk=[[ model_snake_name ]].id)
    [%- endif %]

    [% if "show" in actions -%]
    def show(self[% if not singular %], pk[% endif %]):
        "GET /[[ controller_snake_name ]]/1"
        self._load_[[ model_snake_name ]]([% if not singular %]pk[% endif %])
    [%- endif %]

    [% if "edit" in actions -%]
    def edit(self[% if not singular %], pk[% endif %]):
        "GET /[[ controller_snake_name ]]/1/edit"
        self._load_[[ model_snake_name ]]([% if not singular %]pk[% endif %])
        self.form = [[ model_class_name ]]Form(object=self.[[ model_snake_name ]])
    [%- endif %]

    [% if "update" in actions -%]
    def update(self[% if not singular %], pk[% endif %]):
        "PATCH/PUT /[[ controller_snake_name ]]/1"
        self._load_[[ model_snake_name ]]([% if not singular %]pk[% endif %])
        self.form = [[ model_class_name ]]Form(self.req.form, object=self.[[ model_snake_name ]])
        if not self.form.validate():
            self.resp.template = "edit"
            return

        self.form.save()
        db.s.commit()
        self.resp.flash("[[ model_class_name ]] updated")
        self.resp.redirect_to("[[ controller_class_name ]].show", pk=pk)
    [%- endif %]

    [% if "delete" in actions -%]
    def delete(self[% if not singular %], pk[% endif %]):
        "DELETE /[[ controller_snake_name ]]/1"
        [[ model_snake_name ]] = db.s.get([[ model_class_name ]], pk)
        if [[ model_snake_name ]]:  # deleting twice does not fail
            db.s.delete([[ model_snake_name ]])
            db.s.commit()
        self.resp.flash("[[ model_class_name ]] deleted")
        self.resp.redirect_to("[[ controller_class_name ]].index")
    [%- endif %]

    # Private

    def _load_[[ model_snake_name ]](self[% if not singular %], pk[% endif %]):
        self.[[ model_snake_name ]] = db.s.get([[ model_class_name ]], pk)
        if not self.[[ model_snake_name ]]:
            raise NotFound
