import proper.forms as f

from [[ app_name ]].models import [[ singular_pascal ]]


class [[ singular_pascal ]]Form(f.Form):
    _model = [[ singular_pascal ]]

    [% for f in form_fields -%]
    [[ f.name ]] = f.[[ f.fclass ]]([% if f.required %]required=True[% endif %])
    [% endfor %]
