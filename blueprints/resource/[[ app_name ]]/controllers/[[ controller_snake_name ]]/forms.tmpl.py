import proper_forms as f

from [[ app_name ]].models import [[ model_class_name ]]


class [[ model_class_name ]]Form(f.Form):
    _model = [[ model_class_name ]]

    [% for name, fclass, required in form_fields -%]
    [[ name ]] = f.[[ fclass ]]([% if required %]required=True[% endif %])
    [% endfor %]
