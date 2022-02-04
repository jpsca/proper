import proper_forms as f

from [[ app_name ]].models import [[ singular_pascal ]]


class [[ singular_pascal ]]Form(f.Form):
    _model = [[ singular_pascal ]]

    [% for name, fclass, required in form_fields -%]
    [[ name ]] = f.[[ fclass ]]([% if required %]required=True[% endif %])
    [% endfor %]
