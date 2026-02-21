[% set show_load_method = "show" in actions or "edit" in actions or "update" in actions or "delete" in actions -%]
from proper.errors import NotFound
from proper.status import unprocessable

from ..forms.[[ name_snake ]] import [[ form_class ]]
from ..models import [[ name_pascal ]]
from ..router import router
from .app_controller import AppController


@router.resource("[[ plural_snake ]]"
    [%- if singular %], pk=None
    [%- elif pk %], pk="[[ pk ]]"
    [%- endif -%]
)
class [[ name_pascal ]]Controller(AppController):
    [% if show_load_method -%]
    before = {"do": "[[ load_method ]]"
    [%- if "index" in actions or "new" in actions or "create" in actions -%]
    , "exclude": (
        [%- if "index" in actions %]"index", [% endif -%]
        [%- if "new" in actions %]"new", [% endif -%]
        [%- if "create" in actions %]"create", [% endif -%]
    )[% endif %]}

    [% endif -%]
[% if "index" in actions -%]
    def index(self):
        self.[[ plural_snake ]] = [[ name_pascal ]].select()
[% endif %]
    [% if "show" in actions -%]
    def show(self):
        pass
[% endif %]
    [% if "new" in actions -%]
    def new(self):
        self.form = [[ form_class ]]()
[% endif %]
    [% if "edit" in actions -%]
    def edit(self):
        self.form = [[ form_class ]](object=[[ object ]])
[% endif %]
    [% if "create" in actions -%]
    def create(self):
        self.form = [[ form_class ]](self.params)
        if self.form.is_invalid:
            return self.render("pages/[[ name_snake ]]/new.jinja", status=unprocessable)

        [[ name_snake ]] = self.form.save()
        [[ name_snake ]].save()
        self.response.redirect_to(
            "[[ name_pascal ]].show",
            [[ object_id ]]=[[ name_snake ]].id,
            flash="[[ name_pascal ]] was created",
        )
[% endif %]
    [% if "update" in actions -%]
    def update(self):
        self.form = [[ form_class ]](self.params, object=[[ object ]])
        if self.form.is_invalid:
            return self.render("pages/[[ name_snake ]]/edit.jinja", status=unprocessable)

        [[ name_snake ]] = self.form.save()
        [[ name_snake ]].save()
        self.response.redirect_to(
            "[[ name_pascal ]].show",
            [[ object_id ]]=[[ object ]].id,
            flash="[[ name_pascal ]] was updated",
        )
[% endif %]
    [% if "delete" in actions -%]
    def delete(self):
        if [[ object ]]:  # deleting twice does not fail
            [[ object ]].delete_instance()
        self.response.redirect_to(
            "[[ name_pascal ]].index",
            flash="[[ name_pascal ]] was deleted",
        )
[% endif %]
    [% if show_load_method -%]
    def [[ load_method ]](self):
        [% if singular -%]
        [[ object ]] = [[ name_pascal ]].get_or_none()
        [% else -%]
        [[ object_id ]] = self.params.get("[[ object_id ]]", "")
        if not [[ object_id ]].isdigit():
            raise NotFound
        [[ object ]] = [[ name_pascal ]].get_or_none(int([[ object_id ]]))
        [% endif -%]
        if self.request.matched_action != "delete" and not [[ object ]]:
            raise NotFound
[%- endif %]
